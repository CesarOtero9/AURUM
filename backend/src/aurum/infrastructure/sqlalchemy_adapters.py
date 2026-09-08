"""PostgreSQL adapters bound to the active UnitOfWork session only."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from aurum.application.cfdi_ingestion import (
    CfdiIdentityRepository,
    IdentityRegistration,
    IngestionRecordRepository,
    XmlEvidenceStore,
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
    CfdiIdentityModel,
    IdentityConflictModel,
    IngestionRecordModel,
    XmlEvidenceModel,
)
from aurum.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork


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
