"""PostgreSQL adapters bound to the active UnitOfWork session only."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from aurum.application.cfdi_ingestion import (
    CfdiIdentityRepository,
    IdentityRegistration,
    IngestionRecordRepository,
    XmlEvidenceStore,
)
from aurum.domain.cfdi_concepts import (
    PARSER_NAME as CONCEPTS_PARSER_NAME,
)
from aurum.domain.cfdi_concepts import (
    PARSER_VERSION as CONCEPTS_PARSER_VERSION,
)
from aurum.domain.cfdi_concepts import (
    ParsedCfdiConcepts,
)
from aurum.domain.cfdi_concepts import (
    fingerprint as concepts_fingerprint,
)
from aurum.domain.cfdi_header import (
    PARSER_NAME,
    PARSER_VERSION,
    CfdiFiscalHeader,
    DerivedResultDeterminismViolation,
    HeaderPromotionError,
    ParserFingerprintSchemaMismatch,
    fingerprint,
)
from aurum.domain.cfdi_identity import (
    CfdiIdentity,
    CfdiUuid,
    EvidenceIdentityMismatch,
    IdentityConflict,
    IngestionOutcome,
    OriginalXml,
    Sha256Digest,
    XmlEvidence,
)
from aurum.infrastructure.persistence_models import (
    CfdiConceptModel,
    CfdiConceptsCurrentModel,
    CfdiConceptsParseExecutionModel,
    CfdiConceptsParserSchemaModel,
    CfdiConceptsResultModel,
    CfdiHeaderCurrentModel,
    CfdiHeaderParseExecutionModel,
    CfdiHeaderParserSchemaModel,
    CfdiHeaderResultModel,
    CfdiIdentityModel,
    IdentityConflictModel,
    IngestionRecordModel,
    XmlEvidenceModel,
)
from aurum.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork


def _after_missing_parser_schema() -> None:
    """Private no-op seam for deterministic persistence race tests."""


def _after_missing_header_result() -> None:
    """Private no-op seam for deterministic persistence race tests."""


def _after_missing_concepts_parser_schema() -> None:
    """Private no-op seam for deterministic Concepts persistence race tests."""


def _after_missing_concepts_result() -> None:
    """Private no-op seam for deterministic Concepts persistence race tests."""


def _after_identity_locked() -> None:
    """Private no-op seam for deterministic promotion-lock tests."""


def _uuid(value: CfdiUuid) -> UUID:
    return UUID(value.value)


def _evidence(row: XmlEvidenceModel) -> XmlEvidence:
    return XmlEvidence.from_original_xml(OriginalXml(bytes(row.content)))


class SqlAlchemyXmlEvidenceStore(XmlEvidenceStore):
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def store(self, evidence: XmlEvidence, extracted_uuid: CfdiUuid) -> None:
        session = self._unit_of_work.require_session()
        session.execute(
            insert(XmlEvidenceModel)
            .values(
                sha256=evidence.sha256.value,
                extracted_fiscal_uuid=_uuid(extracted_uuid),
                content=evidence.original_xml.value,
                byte_length=len(evidence.original_xml.value),
            )
            .on_conflict_do_nothing(index_elements=["sha256"])
        )
        row = self.row_for(evidence.sha256)
        if row.extracted_fiscal_uuid != _uuid(extracted_uuid):
            raise EvidenceIdentityMismatch("Evidence digest has another extracted UUID")

    def get_by_digest(self, digest: Sha256Digest) -> CfdiUuid | None:
        row = self._unit_of_work.require_session().scalar(
            select(XmlEvidenceModel.extracted_fiscal_uuid).where(
                XmlEvidenceModel.sha256 == digest.value
            )
        )
        return None if row is None else CfdiUuid.from_raw(str(row))

    def row_for(self, digest: Sha256Digest) -> XmlEvidenceModel:
        row = self._unit_of_work.require_session().scalar(
            select(XmlEvidenceModel).where(XmlEvidenceModel.sha256 == digest.value)
        )
        if row is None:
            raise RuntimeError("Evidence must be stored before it is referenced")
        return row


class SqlAlchemyCfdiIdentityRepository(CfdiIdentityRepository):
    def __init__(
        self, unit_of_work: SqlAlchemyUnitOfWork, evidence_store: SqlAlchemyXmlEvidenceStore
    ) -> None:
        self._unit_of_work, self._evidence_store = unit_of_work, evidence_store

    def get_by_uuid(self, cfdi_uuid: CfdiUuid) -> CfdiIdentity | None:
        row = self._row_by_uuid(cfdi_uuid)
        return None if row is None else self._to_domain(row)

    def get_by_digest(self, digest: Sha256Digest) -> CfdiIdentity | None:
        row = self._unit_of_work.require_session().scalar(
            select(CfdiIdentityModel)
            .join(
                XmlEvidenceModel, CfdiIdentityModel.authoritative_evidence_id == XmlEvidenceModel.id
            )
            .where(XmlEvidenceModel.sha256 == digest.value)
            .with_for_update()
        )
        return None if row is None else self._to_domain(row)

    def register(self, identity: CfdiIdentity) -> IdentityRegistration:
        session = self._unit_of_work.require_session()
        evidence = self._evidence_store.row_for(identity.evidence.sha256)
        try:
            with session.begin_nested():
                session.add(
                    CfdiIdentityModel(
                        fiscal_uuid=_uuid(identity.uuid), authoritative_evidence_id=evidence.id
                    )
                )
                session.flush()
            return IdentityRegistration(identity=identity, created=True)
        except IntegrityError:
            winner = self._row_by_uuid(identity.uuid)
            if winner is None:
                raise
            return IdentityRegistration(identity=self._to_domain(winner), created=False)

    def row_for(self, cfdi_uuid: CfdiUuid) -> CfdiIdentityModel:
        row = self._row_by_uuid(cfdi_uuid)
        if row is None:
            raise RuntimeError("CFDI identity must exist before an ingestion record")
        return row

    def _row_by_uuid(self, cfdi_uuid: CfdiUuid) -> CfdiIdentityModel | None:
        return self._unit_of_work.require_session().scalar(
            select(CfdiIdentityModel)
            .where(CfdiIdentityModel.fiscal_uuid == _uuid(cfdi_uuid))
            .with_for_update()
        )

    def _to_domain(self, row: CfdiIdentityModel) -> CfdiIdentity:
        evidence = self._unit_of_work.require_session().get(
            XmlEvidenceModel, row.authoritative_evidence_id
        )
        assert evidence is not None
        return CfdiIdentity(CfdiUuid.from_raw(str(row.fiscal_uuid)), _evidence(evidence))


class SqlAlchemyIngestionRecordRepository(IngestionRecordRepository):
    def __init__(
        self,
        unit_of_work: SqlAlchemyUnitOfWork,
        identities: SqlAlchemyCfdiIdentityRepository,
        evidence: SqlAlchemyXmlEvidenceStore,
    ) -> None:
        self._unit_of_work, self._identities, self._evidence = unit_of_work, identities, evidence

    def record_accepted(self, identity: CfdiIdentity, evidence: XmlEvidence) -> None:
        self._record_authoritative(IngestionOutcome.ACCEPTED, identity, evidence)

    def record_reingestion(self, identity: CfdiIdentity, evidence: XmlEvidence) -> None:
        self._record_authoritative(IngestionOutcome.REINGESTED, identity, evidence)

    def _record_authoritative(
        self, outcome: IngestionOutcome, identity: CfdiIdentity, evidence: XmlEvidence
    ) -> None:
        identity_row = self._identities.row_for(identity.uuid)
        evidence_row = self._evidence.row_for(evidence.sha256)
        self._unit_of_work.require_session().add(
            IngestionRecordModel(
                outcome=outcome.value,
                evidence_id=evidence_row.id,
                cfdi_identity_id=identity_row.id,
                authoritative_evidence_id=identity_row.authoritative_evidence_id,
            )
        )

    def record_conflict(self, conflict: IdentityConflict) -> None:
        session = self._unit_of_work.require_session()
        identity_row = self._identities.row_for(conflict.existing_identity.uuid)
        incoming = self._evidence.row_for(conflict.incoming_evidence.sha256)
        session.execute(
            insert(IdentityConflictModel)
            .values(
                cfdi_identity_id=identity_row.id,
                incoming_evidence_id=incoming.id,
                fiscal_uuid=_uuid(conflict.existing_identity.uuid),
            )
            .on_conflict_do_nothing(index_elements=["cfdi_identity_id", "incoming_evidence_id"])
        )
        incident = session.scalar(
            select(IdentityConflictModel).where(
                IdentityConflictModel.cfdi_identity_id == identity_row.id,
                IdentityConflictModel.incoming_evidence_id == incoming.id,
            )
        )
        assert incident is not None
        session.add(
            IngestionRecordModel(
                outcome=IngestionOutcome.IDENTITY_CONFLICT.value,
                evidence_id=incoming.id,
                cfdi_identity_id=identity_row.id,
                authoritative_evidence_id=identity_row.authoritative_evidence_id,
                identity_conflict_id=incident.id,
            )
        )


class SqlAlchemyCfdiHeaderRepository:
    """Append-only header result/execution persistence within an active UoW."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def record_success(
        self,
        evidence_id: int,
        header: CfdiFiscalHeader,
        configuration_hash: str,
        implementation_id: str | None = None,
    ) -> CfdiHeaderResultModel:
        session = self._unit_of_work.require_session()
        schema, digest = fingerprint(header)
        parser_schema = session.scalar(
            select(CfdiHeaderParserSchemaModel).where(
                CfdiHeaderParserSchemaModel.parser_name == PARSER_NAME,
                CfdiHeaderParserSchemaModel.parser_version == PARSER_VERSION,
            )
        )
        if parser_schema is None:
            _after_missing_parser_schema()
            try:
                with session.begin_nested():
                    session.add(
                        CfdiHeaderParserSchemaModel(
                            parser_name=PARSER_NAME,
                            parser_version=PARSER_VERSION,
                            result_fingerprint_schema=schema,
                        )
                    )
                    session.flush()
            except IntegrityError:
                parser_schema = session.scalar(
                    select(CfdiHeaderParserSchemaModel).where(
                        CfdiHeaderParserSchemaModel.parser_name == PARSER_NAME,
                        CfdiHeaderParserSchemaModel.parser_version == PARSER_VERSION,
                    )
                )
        if parser_schema is not None and parser_schema.result_fingerprint_schema != schema:
            raise ParserFingerprintSchemaMismatch("Fingerprint schema changed for parser identity")
        existing = session.scalar(
            select(CfdiHeaderResultModel).where(
                CfdiHeaderResultModel.evidence_id == evidence_id,
                CfdiHeaderResultModel.parser_name == PARSER_NAME,
                CfdiHeaderResultModel.parser_version == PARSER_VERSION,
                CfdiHeaderResultModel.configuration_hash == configuration_hash,
            )
        )
        if existing is not None:
            if existing.result_fingerprint_schema != schema:
                raise ParserFingerprintSchemaMismatch(
                    "Fingerprint schema changed for parser identity"
                )
            if existing.result_fingerprint != digest:
                raise DerivedResultDeterminismViolation(
                    "Fingerprint changed for logical result identity"
                )
            result = existing
        else:
            _after_missing_header_result()
            c, issuer, receiver = header.comprobante, header.issuer, header.receiver
            result = CfdiHeaderResultModel(
                evidence_id=evidence_id,
                parser_name=PARSER_NAME,
                parser_version=PARSER_VERSION,
                configuration_hash=configuration_hash,
                result_fingerprint_schema=schema,
                result_fingerprint=digest,
                cfdi_schema_version=header.version.value,
                fecha_source=c.fecha.source,
                fecha=c.fecha.value,
                tipo_comprobante=c.tipo_comprobante,
                serie_source=c.serie,
                folio_source=c.folio,
                moneda=c.moneda,
                tipo_cambio_source=None if c.tipo_cambio is None else c.tipo_cambio.source,
                tipo_cambio=None if c.tipo_cambio is None else c.tipo_cambio.value,
                subtotal_source=c.subtotal.source,
                subtotal=c.subtotal.value,
                descuento_source=None if c.descuento is None else c.descuento.source,
                descuento=None if c.descuento is None else c.descuento.value,
                total_source=c.total.source,
                total=c.total.value,
                exportacion=c.exportacion,
                lugar_expedicion=c.lugar_expedicion,
                metodo_pago=c.metodo_pago,
                forma_pago=c.forma_pago,
                condiciones_pago_source=c.condiciones_pago,
                confirmacion_source=c.confirmacion,
                issuer_rfc_source=issuer.rfc.source,
                issuer_rfc_canonical=issuer.rfc.canonical,
                issuer_nombre_source=issuer.nombre,
                issuer_regimen_fiscal=issuer.regimen_fiscal,
                receiver_rfc_source=receiver.rfc.source,
                receiver_rfc_canonical=receiver.rfc.canonical,
                receiver_nombre_source=receiver.nombre,
                domicilio_fiscal_receptor=receiver.domicilio_fiscal_receptor,
                regimen_fiscal_receptor=receiver.regimen_fiscal_receptor,
                uso_cfdi=receiver.uso_cfdi,
            )
            try:
                with session.begin_nested():
                    session.add(result)
                    session.flush()
            except IntegrityError:
                winner = session.scalar(
                    select(CfdiHeaderResultModel).where(
                        CfdiHeaderResultModel.evidence_id == evidence_id,
                        CfdiHeaderResultModel.parser_name == PARSER_NAME,
                        CfdiHeaderResultModel.parser_version == PARSER_VERSION,
                        CfdiHeaderResultModel.configuration_hash == configuration_hash,
                    )
                )
                if winner is None:
                    raise
                if winner.result_fingerprint_schema != schema:
                    raise ParserFingerprintSchemaMismatch(
                        "Fingerprint schema changed for parser identity"
                    )
                if winner.result_fingerprint != digest:
                    raise DerivedResultDeterminismViolation(
                        "Fingerprint changed for logical result identity"
                    )
                result = winner
        session.add(
            CfdiHeaderParseExecutionModel(
                evidence_id=evidence_id,
                parser_name=PARSER_NAME,
                parser_version=PARSER_VERSION,
                configuration_hash=configuration_hash,
                status="SUCCEEDED",
                result_id=result.id,
                implementation_id=implementation_id,
            )
        )
        return result

    def record_failure(self, evidence_id: int, configuration_hash: str, error: Exception) -> None:
        self._unit_of_work.require_session().add(
            CfdiHeaderParseExecutionModel(
                evidence_id=evidence_id,
                parser_name=PARSER_NAME,
                parser_version=PARSER_VERSION,
                configuration_hash=configuration_hash,
                status="FAILED",
                error_code=type(error).__name__,
                error_type=type(error).__name__,
                error_message=str(error),
            )
        )

    def promote(self, identity_id: int, result_id: int) -> None:
        session = self._unit_of_work.require_session()
        identity = session.scalar(
            select(CfdiIdentityModel).where(CfdiIdentityModel.id == identity_id).with_for_update()
        )
        _after_identity_locked()
        result = session.get(CfdiHeaderResultModel, result_id)
        if (
            identity is None
            or result is None
            or result.evidence_id != identity.authoritative_evidence_id
        ):
            raise HeaderPromotionError("Result is not derived from authoritative identity evidence")
        session.execute(
            insert(CfdiHeaderCurrentModel)
            .values(
                cfdi_identity_id=identity.id, evidence_id=result.evidence_id, result_id=result.id
            )
            .on_conflict_do_update(
                index_elements=["cfdi_identity_id"],
                set_={
                    "evidence_id": result.evidence_id,
                    "result_id": result.id,
                    "promoted_at": func.now(),
                },
            )
        )


class SqlAlchemyCfdiConceptsRepository:
    """Append-only Concepts result/execution persistence within an active UoW."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def record_success(
        self,
        evidence_id: int,
        concepts: ParsedCfdiConcepts,
        configuration_hash: str,
        implementation_id: str | None = None,
    ) -> CfdiConceptsResultModel:
        self._validate(concepts)
        session = self._unit_of_work.require_session()
        schema, digest = concepts_fingerprint(concepts)
        parser_schema = session.scalar(
            select(CfdiConceptsParserSchemaModel).where(
                CfdiConceptsParserSchemaModel.parser_name == CONCEPTS_PARSER_NAME,
                CfdiConceptsParserSchemaModel.parser_version == CONCEPTS_PARSER_VERSION,
            )
        )
        if parser_schema is None:
            _after_missing_concepts_parser_schema()
            try:
                with session.begin_nested():
                    session.add(
                        CfdiConceptsParserSchemaModel(
                            parser_name=CONCEPTS_PARSER_NAME,
                            parser_version=CONCEPTS_PARSER_VERSION,
                            result_fingerprint_schema=schema,
                        )
                    )
                    session.flush()
            except IntegrityError:
                parser_schema = session.scalar(
                    select(CfdiConceptsParserSchemaModel).where(
                        CfdiConceptsParserSchemaModel.parser_name == CONCEPTS_PARSER_NAME,
                        CfdiConceptsParserSchemaModel.parser_version == CONCEPTS_PARSER_VERSION,
                    )
                )
        if parser_schema is not None and parser_schema.result_fingerprint_schema != schema:
            raise ParserFingerprintSchemaMismatch("Fingerprint schema changed for parser identity")
        existing = session.scalar(
            select(CfdiConceptsResultModel).where(
                CfdiConceptsResultModel.evidence_id == evidence_id,
                CfdiConceptsResultModel.parser_name == CONCEPTS_PARSER_NAME,
                CfdiConceptsResultModel.parser_version == CONCEPTS_PARSER_VERSION,
                CfdiConceptsResultModel.configuration_hash == configuration_hash,
            )
        )
        if existing is not None:
            if existing.result_fingerprint_schema != schema:
                raise ParserFingerprintSchemaMismatch(
                    "Fingerprint schema changed for parser identity"
                )
            if existing.result_fingerprint != digest:
                raise DerivedResultDeterminismViolation(
                    "Fingerprint changed for logical result identity"
                )
            result = existing
        else:
            _after_missing_concepts_result()
            result = CfdiConceptsResultModel(
                evidence_id=evidence_id,
                parser_name=CONCEPTS_PARSER_NAME,
                parser_version=CONCEPTS_PARSER_VERSION,
                configuration_hash=configuration_hash,
                cfdi_version=concepts.version.value,
                concept_count=len(concepts.concepts),
                result_fingerprint_schema=schema,
                result_fingerprint=digest,
            )
            try:
                with session.begin_nested():
                    session.add(result)
                    session.flush()
                    session.add_all(
                        [
                            CfdiConceptModel(
                                result_id=result.id,
                                concept_index=item.concept_index,
                                clave_prod_serv_raw=item.clave_prod_serv_raw,
                                no_identificacion_raw=item.no_identificacion_raw,
                                cantidad_raw=item.cantidad_raw,
                                cantidad=item.cantidad,
                                clave_unidad_raw=item.clave_unidad_raw,
                                unidad_raw=item.unidad_raw,
                                descripcion_raw=item.descripcion_raw,
                                valor_unitario_raw=item.valor_unitario_raw,
                                valor_unitario=item.valor_unitario,
                                importe_raw=item.importe_raw,
                                importe=item.importe,
                                descuento_raw=item.descuento_raw,
                                descuento=item.descuento,
                                objeto_imp_raw=item.objeto_imp_raw,
                            )
                            for item in concepts.concepts
                        ]
                    )
                    session.flush()
            except IntegrityError:
                winner = session.scalar(
                    select(CfdiConceptsResultModel).where(
                        CfdiConceptsResultModel.evidence_id == evidence_id,
                        CfdiConceptsResultModel.parser_name == CONCEPTS_PARSER_NAME,
                        CfdiConceptsResultModel.parser_version == CONCEPTS_PARSER_VERSION,
                        CfdiConceptsResultModel.configuration_hash == configuration_hash,
                    )
                )
                if winner is None:
                    raise
                if winner.result_fingerprint_schema != schema:
                    raise ParserFingerprintSchemaMismatch(
                        "Fingerprint schema changed for parser identity"
                    )
                if winner.result_fingerprint != digest:
                    raise DerivedResultDeterminismViolation(
                        "Fingerprint changed for logical result identity"
                    )
                result = winner
        session.add(
            CfdiConceptsParseExecutionModel(
                evidence_id=evidence_id,
                parser_name=CONCEPTS_PARSER_NAME,
                parser_version=CONCEPTS_PARSER_VERSION,
                configuration_hash=configuration_hash,
                status="SUCCEEDED",
                result_id=result.id,
                implementation_id=implementation_id,
            )
        )
        return result

    def record_failure(self, evidence_id: int, configuration_hash: str, error: Exception) -> None:
        self._unit_of_work.require_session().add(
            CfdiConceptsParseExecutionModel(
                evidence_id=evidence_id,
                parser_name=CONCEPTS_PARSER_NAME,
                parser_version=CONCEPTS_PARSER_VERSION,
                configuration_hash=configuration_hash,
                status="FAILED",
                error_code=type(error).__name__,
                error_type=type(error).__name__,
                error_message=str(error),
            )
        )

    def get_current(self, identity_id: int) -> CfdiConceptsCurrentModel | None:
        return self._unit_of_work.require_session().get(CfdiConceptsCurrentModel, identity_id)

    def promote(self, identity_id: int, result_id: int) -> None:
        session = self._unit_of_work.require_session()
        identity = session.scalar(
            select(CfdiIdentityModel).where(CfdiIdentityModel.id == identity_id).with_for_update()
        )
        _after_identity_locked()
        result = session.get(CfdiConceptsResultModel, result_id)
        if (
            identity is None
            or result is None
            or result.evidence_id != identity.authoritative_evidence_id
        ):
            raise HeaderPromotionError("Result is not derived from authoritative identity evidence")
        session.execute(
            insert(CfdiConceptsCurrentModel)
            .values(
                cfdi_identity_id=identity.id, evidence_id=result.evidence_id, result_id=result.id
            )
            .on_conflict_do_update(
                index_elements=["cfdi_identity_id"],
                set_={
                    "evidence_id": result.evidence_id,
                    "result_id": result.id,
                    "promoted_at": func.now(),
                },
            )
        )

    @staticmethod
    def _validate(concepts: ParsedCfdiConcepts) -> None:
        if not concepts.concepts:
            raise ValueError("Concepts result must contain at least one concept")
        if [item.concept_index for item in concepts.concepts] != list(
            range(len(concepts.concepts))
        ):
            raise ValueError("Concept indexes must be contiguous and zero-based")
        for item in concepts.concepts:
            if (item.descuento_raw is None) != (item.descuento is None):
                raise ValueError("Discount raw and parsed values must be paired")
            if concepts.version.value == "3.3" and item.objeto_imp_raw is not None:
                raise ValueError("CFDI 3.3 concepts cannot contain ObjetoImp")
            if concepts.version.value == "4.0" and item.objeto_imp_raw is None:
                raise ValueError("CFDI 4.0 concepts require ObjetoImp")
