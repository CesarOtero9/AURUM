from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from aurum.domain.cfdi_identity import (
    CfdiIdentity,
    CfdiUuid,
    EvidenceIdentityMismatch,
    EvidenceStorageFailure,
    IdentityConflict,
    IdentityPersistenceFailure,
    IngestionOutcome,
    IngestionResult,
    OriginalXml,
    Sha256Digest,
    XmlEvidence,
)


class CfdiIdentityReader(Protocol):
    def read_uuid(self, original_xml: OriginalXml) -> CfdiUuid: ...


class XmlEvidenceStore(Protocol):
    def store(self, evidence: XmlEvidence, extracted_uuid: CfdiUuid) -> None: ...

    def get_by_digest(self, digest: Sha256Digest) -> CfdiUuid | None: ...


@dataclass(frozen=True, slots=True)
class IdentityRegistration:
    identity: CfdiIdentity
    created: bool


class CfdiIdentityRepository(Protocol):
    def get_by_uuid(self, cfdi_uuid: CfdiUuid) -> CfdiIdentity | None: ...

    def get_by_digest(self, digest: Sha256Digest) -> CfdiIdentity | None: ...

    def register(self, identity: CfdiIdentity) -> IdentityRegistration: ...


class IngestionRecordRepository(Protocol):
    def record_accepted(self, identity: CfdiIdentity, evidence: XmlEvidence) -> None: ...

    def record_reingestion(self, identity: CfdiIdentity, evidence: XmlEvidence) -> None: ...

    def record_conflict(self, conflict: IdentityConflict) -> None: ...


class UnitOfWork(Protocol):
    def __enter__(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class IngestCfdiXml:
    def __init__(
        self,
        reader: CfdiIdentityReader,
        evidence_store: XmlEvidenceStore,
        identity_repository: CfdiIdentityRepository,
        ingestion_records: IngestionRecordRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._reader = reader
        self._evidence_store = evidence_store
        self._identity_repository = identity_repository
        self._ingestion_records = ingestion_records
        self._unit_of_work = unit_of_work

    def ingest_cfdi_xml(self, original_xml: bytes) -> IngestionResult:
        evidence = XmlEvidence.from_original_xml(OriginalXml(original_xml))
        cfdi_uuid = self._reader.read_uuid(evidence.original_xml)

        try:
            with self._unit_of_work:
                by_digest = self._identity_repository.get_by_digest(evidence.sha256)
                if by_digest is not None and by_digest.uuid != cfdi_uuid:
                    raise EvidenceIdentityMismatch(
                        "Evidence digest is already associated with another CFDI UUID"
                    )
                # Evidence is persisted before identity resolution.  Its adapter checks that
                # a pre-existing digest was extracted from the same fiscal UUID (case D).
                self._evidence_store.store(evidence, cfdi_uuid)
                evidence_uuid = self._evidence_store.get_by_digest(evidence.sha256)
                if evidence_uuid is not None and evidence_uuid != cfdi_uuid:
                    raise EvidenceIdentityMismatch(
                        "Evidence digest is already associated with another CFDI UUID"
                    )

                by_uuid = self._identity_repository.get_by_uuid(cfdi_uuid)
                if by_uuid is not None:
                    if by_uuid.evidence.sha256 == evidence.sha256:
                        self._ingestion_records.record_reingestion(by_uuid, evidence)
                        return IngestionResult(
                            outcome=IngestionOutcome.REINGESTED,
                            cfdi_identity=by_uuid,
                            evidence=by_uuid.evidence,
                        )

                    self._ingestion_records.record_conflict(
                        IdentityConflict(existing_identity=by_uuid, incoming_evidence=evidence)
                    )
                    return IngestionResult(
                        outcome=IngestionOutcome.IDENTITY_CONFLICT,
                        cfdi_identity=by_uuid,
                        evidence=evidence,
                    )

                identity = CfdiIdentity(uuid=cfdi_uuid, evidence=evidence)
                registration = self._identity_repository.register(identity)
                persisted_identity = registration.identity
                if (
                    not registration.created
                    and persisted_identity.evidence.sha256 == evidence.sha256
                ):
                    self._ingestion_records.record_reingestion(persisted_identity, evidence)
                    return IngestionResult(
                        outcome=IngestionOutcome.REINGESTED,
                        cfdi_identity=persisted_identity,
                        evidence=persisted_identity.evidence,
                    )
                if not registration.created:
                    self._ingestion_records.record_conflict(
                        IdentityConflict(
                            existing_identity=persisted_identity, incoming_evidence=evidence
                        )
                    )
                    return IngestionResult(
                        outcome=IngestionOutcome.IDENTITY_CONFLICT,
                        cfdi_identity=persisted_identity,
                        evidence=evidence,
                    )
                self._ingestion_records.record_accepted(persisted_identity, evidence)
                return IngestionResult(
                    outcome=IngestionOutcome.ACCEPTED,
                    cfdi_identity=persisted_identity,
                    evidence=evidence,
                )
        except EvidenceIdentityMismatch:
            raise
        except EvidenceStorageFailure:
            raise
        except IdentityPersistenceFailure:
            raise
        except Exception as error:
            raise IdentityPersistenceFailure("Unable to persist CFDI identity") from error
