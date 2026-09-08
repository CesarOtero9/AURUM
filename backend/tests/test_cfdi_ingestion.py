from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from hashlib import sha256

import pytest

from aurum.application.cfdi_ingestion import IdentityRegistration, IngestCfdiXml
from aurum.domain.cfdi_identity import (
    CfdiIdentity,
    CfdiUuid,
    EvidenceIdentityMismatch,
    EvidenceStorageFailure,
    IdentityConflict,
    IngestionOutcome,
    InvalidCfdiUuid,
    MalformedXml,
    MissingTimbreFiscalDigital,
    MissingTimbreUuid,
    MultipleTimbreFiscalDigital,
    OriginalXml,
    Sha256Digest,
    XmlEvidence,
    XmlInputTooLarge,
)
from aurum.infrastructure.xml_cfdi_identity_reader import SecureCfdiIdentityReader

SAT_TIMBRE_NAMESPACE = "http://www.sat.gob.mx/TimbreFiscalDigital"
VALID_UUID = "039D171E-773B-495C-881F-BBEFBC8991C2"


def cfdi_xml(uuid: str = VALID_UUID, timbre_namespace: str = SAT_TIMBRE_NAMESPACE) -> bytes:
    return (
        "<cfdi:Comprobante xmlns:cfdi='http://www.sat.gob.mx/cfd/4' "
        f"xmlns:tfd='{timbre_namespace}'>"
        f"<cfdi:Complemento><tfd:TimbreFiscalDigital UUID='{uuid}' /></cfdi:Complemento>"
        "</cfdi:Comprobante>"
    ).encode()


@dataclass
class InMemoryIdentityRepository:
    identities_by_uuid: dict[CfdiUuid, CfdiIdentity] = field(default_factory=dict)
    identities_by_digest: dict[Sha256Digest, CfdiIdentity] = field(default_factory=dict)

    def get_by_uuid(self, cfdi_uuid: CfdiUuid) -> CfdiIdentity | None:
        return self.identities_by_uuid.get(cfdi_uuid)

    def get_by_digest(self, digest: Sha256Digest) -> CfdiIdentity | None:
        return self.identities_by_digest.get(digest)

    def register(self, identity: CfdiIdentity) -> IdentityRegistration:
        existing = self.identities_by_uuid.get(identity.uuid)
        if existing is not None:
            return IdentityRegistration(identity=existing, created=False)
        self.identities_by_uuid[identity.uuid] = identity
        self.identities_by_digest[identity.evidence.sha256] = identity
        return IdentityRegistration(identity=identity, created=True)


@dataclass
class InMemoryEvidenceStore:
    evidence_by_digest: dict[Sha256Digest, XmlEvidence] = field(default_factory=dict)

    extracted_by_digest: dict[Sha256Digest, CfdiUuid] = field(default_factory=dict)

    def store(self, evidence: XmlEvidence, extracted_uuid: CfdiUuid) -> None:
        existing = self.extracted_by_digest.get(evidence.sha256)
        if existing is not None and existing != extracted_uuid:
            raise EvidenceIdentityMismatch("Evidence digest has another extracted UUID")
        self.evidence_by_digest.setdefault(evidence.sha256, evidence)
        self.extracted_by_digest.setdefault(evidence.sha256, extracted_uuid)

    def get_by_digest(self, digest: Sha256Digest) -> CfdiUuid | None:
        return self.extracted_by_digest.get(digest)


@dataclass
class InMemoryIngestionRecords:
    accepted: list[tuple[CfdiIdentity, XmlEvidence]] = field(default_factory=list)
    reingestions: list[tuple[CfdiIdentity, XmlEvidence]] = field(default_factory=list)
    conflicts: list[IdentityConflict] = field(default_factory=list)

    def record_accepted(self, identity: CfdiIdentity, evidence: XmlEvidence) -> None:
        self.accepted.append((identity, evidence))

    def record_reingestion(self, identity: CfdiIdentity, evidence: XmlEvidence) -> None:
        self.reingestions.append((identity, evidence))

    def record_conflict(self, conflict: IdentityConflict) -> None:
        self.conflicts.append(conflict)


class InMemoryUnitOfWork(AbstractContextManager[None]):
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None


@dataclass
class IngestionFixture:
    repository: InMemoryIdentityRepository = field(default_factory=InMemoryIdentityRepository)
    evidence_store: InMemoryEvidenceStore = field(default_factory=InMemoryEvidenceStore)
    records: InMemoryIngestionRecords = field(default_factory=InMemoryIngestionRecords)

    def create_use_case(self) -> IngestCfdiXml:
        return IngestCfdiXml(
            reader=SecureCfdiIdentityReader(),
            evidence_store=self.evidence_store,
            identity_repository=self.repository,
            ingestion_records=self.records,
            unit_of_work=InMemoryUnitOfWork(),
        )


@pytest.fixture
def ingestion() -> IngestionFixture:
    return IngestionFixture()


def test_accepts_valid_xml_and_canonicalizes_uuid(ingestion: IngestionFixture) -> None:
    result = ingestion.create_use_case().ingest_cfdi_xml(cfdi_xml(VALID_UUID.lower()))

    assert result.outcome is IngestionOutcome.ACCEPTED
    assert result.cfdi_identity.uuid.value == VALID_UUID


def test_uuid_comparison_is_case_insensitive_at_input(ingestion: IngestionFixture) -> None:
    reader = SecureCfdiIdentityReader()
    first = reader.read_uuid(OriginalXml(cfdi_xml(VALID_UUID.lower())))
    second = reader.read_uuid(OriginalXml(cfdi_xml(VALID_UUID)))

    assert first == second
    assert second.value == VALID_UUID


def test_uuid_outside_exact_sat_timbre_does_not_establish_identity(
    ingestion: IngestionFixture,
) -> None:
    xml = b"<root UUID='039D171E-773B-495C-881F-BBEFBC8991C2' />"

    with pytest.raises(MissingTimbreFiscalDigital):
        ingestion.create_use_case().ingest_cfdi_xml(xml)


def test_timbre_in_wrong_namespace_does_not_establish_identity(
    ingestion: IngestionFixture,
) -> None:
    with pytest.raises(MissingTimbreFiscalDigital):
        ingestion.create_use_case().ingest_cfdi_xml(cfdi_xml(timbre_namespace="urn:wrong"))


def test_xml_without_timbre_is_rejected(ingestion: IngestionFixture) -> None:
    with pytest.raises(MissingTimbreFiscalDigital):
        ingestion.create_use_case().ingest_cfdi_xml(b"<root />")


def test_timbre_without_uuid_is_rejected(ingestion: IngestionFixture) -> None:
    xml = (
        "<root xmlns:tfd='http://www.sat.gob.mx/TimbreFiscalDigital'>"
        "<tfd:TimbreFiscalDigital /></root>"
    ).encode()

    with pytest.raises(MissingTimbreUuid):
        ingestion.create_use_case().ingest_cfdi_xml(xml)


def test_multiple_exact_sat_timbres_are_rejected(ingestion: IngestionFixture) -> None:
    xml = (
        "<root xmlns:tfd='http://www.sat.gob.mx/TimbreFiscalDigital'>"
        f"<tfd:TimbreFiscalDigital UUID='{VALID_UUID}' />"
        f"<tfd:TimbreFiscalDigital UUID='{VALID_UUID}' />"
        "</root>"
    ).encode()

    with pytest.raises(MultipleTimbreFiscalDigital):
        ingestion.create_use_case().ingest_cfdi_xml(xml)


def test_invalid_uuid_is_rejected(ingestion: IngestionFixture) -> None:
    with pytest.raises(InvalidCfdiUuid):
        ingestion.create_use_case().ingest_cfdi_xml(cfdi_xml("not-a-uuid"))


@pytest.mark.parametrize(
    "raw_uuid",
    [
        "039D171E773B495C881FBBEFBC8991C2",
        "{039D171E-773B-495C-881F-BBEFBC8991C2}",
        "urn:uuid:039D171E-773B-495C-881F-BBEFBC8991C2",
        "039D171E-773B-495C-881F-BBEFBC8991CZ",
    ],
)
def test_non_sat_lexical_uuid_formats_are_rejected(raw_uuid: str) -> None:
    with pytest.raises(InvalidCfdiUuid):
        CfdiUuid.from_raw(raw_uuid)


def test_malformed_xml_is_rejected(ingestion: IngestionFixture) -> None:
    with pytest.raises(MalformedXml):
        ingestion.create_use_case().ingest_cfdi_xml(b"<root>")


@pytest.mark.parametrize(
    "xml",
    [
        b"<!DOCTYPE root [<!ENTITY xxe SYSTEM 'https://example.test'>]><root>&xxe;</root>",
        b"<!ENTITY xxe 'unsafe'><root>&xxe;</root>",
    ],
)
def test_unsafe_xml_is_rejected(ingestion: IngestionFixture, xml: bytes) -> None:
    with pytest.raises(MalformedXml):
        ingestion.create_use_case().ingest_cfdi_xml(xml)


def test_sha256_is_calculated_from_exact_original_bytes(ingestion: IngestionFixture) -> None:
    xml = b"\n" + cfdi_xml() + b"\n"
    result = ingestion.create_use_case().ingest_cfdi_xml(xml)

    assert result.evidence.sha256.value == sha256(xml).hexdigest()


def test_case_a_and_c_are_idempotent_reingestion(ingestion: IngestionFixture) -> None:
    use_case = ingestion.create_use_case()
    xml = cfdi_xml()
    accepted = use_case.ingest_cfdi_xml(xml)
    reingested = use_case.ingest_cfdi_xml(xml)

    assert accepted.outcome is IngestionOutcome.ACCEPTED
    assert reingested.outcome is IngestionOutcome.REINGESTED
    assert len(ingestion.repository.identities_by_uuid) == 1
    assert len(ingestion.evidence_store.evidence_by_digest) == 1
    assert len(ingestion.records.reingestions) == 1


@pytest.mark.parametrize("same_evidence", [True, False])
def test_lost_identity_registration_race_uses_winner_outcome(same_evidence: bool) -> None:
    incoming = XmlEvidence.from_original_xml(OriginalXml(cfdi_xml()))
    winner_evidence = (
        incoming
        if same_evidence
        else XmlEvidence.from_original_xml(
            OriginalXml(cfdi_xml().replace(b"<cfdi:Complemento>", b"<cfdi:Complemento> "))
        )
    )
    winner = CfdiIdentity(CfdiUuid.from_raw(VALID_UUID), winner_evidence)

    class LostRaceRepository(InMemoryIdentityRepository):
        def get_by_uuid(self, cfdi_uuid: CfdiUuid) -> CfdiIdentity | None:
            return None

        def register(self, identity: CfdiIdentity) -> IdentityRegistration:
            return IdentityRegistration(identity=winner, created=False)

    records = InMemoryIngestionRecords()
    use_case = IngestCfdiXml(
        SecureCfdiIdentityReader(),
        InMemoryEvidenceStore(),
        LostRaceRepository(),
        records,
        InMemoryUnitOfWork(),
    )
    result = use_case.ingest_cfdi_xml(cfdi_xml())

    expected = IngestionOutcome.REINGESTED if same_evidence else IngestionOutcome.IDENTITY_CONFLICT
    assert result.outcome is expected
    assert len(records.reingestions) == int(same_evidence)
    assert len(records.conflicts) == int(not same_evidence)


def test_case_b_preserves_conflict_without_replacing_evidence(ingestion: IngestionFixture) -> None:
    use_case = ingestion.create_use_case()
    accepted = use_case.ingest_cfdi_xml(cfdi_xml())
    conflicting_xml = cfdi_xml().replace(b"<cfdi:Complemento>", b"<cfdi:Complemento> ")
    conflict = use_case.ingest_cfdi_xml(conflicting_xml)

    assert conflict.outcome is IngestionOutcome.IDENTITY_CONFLICT
    assert conflict.cfdi_identity == accepted.cfdi_identity
    assert conflict.evidence.sha256 != accepted.evidence.sha256
    assert ingestion.repository.get_by_uuid(accepted.cfdi_identity.uuid) == accepted.cfdi_identity
    assert len(ingestion.evidence_store.evidence_by_digest) == 2
    assert len(ingestion.records.conflicts) == 1


def test_uuid_casing_changes_bytes_and_creates_identity_conflict(
    ingestion: IngestionFixture,
) -> None:
    use_case = ingestion.create_use_case()
    accepted = use_case.ingest_cfdi_xml(cfdi_xml(VALID_UUID.lower()))
    conflict = use_case.ingest_cfdi_xml(cfdi_xml(VALID_UUID))

    assert accepted.cfdi_uuid == conflict.cfdi_uuid
    assert accepted.sha256 != conflict.sha256
    assert conflict.outcome is IngestionOutcome.IDENTITY_CONFLICT


def test_max_input_bytes_is_enforced_before_parsing() -> None:
    reader = SecureCfdiIdentityReader(max_input_bytes=1)

    with pytest.raises(XmlInputTooLarge):
        reader.read_uuid(OriginalXml(cfdi_xml()))


def test_max_depth_is_enforced_during_streaming_parse() -> None:
    reader = SecureCfdiIdentityReader(max_depth=1)

    with pytest.raises(MalformedXml, match="structural safety limits"):
        reader.read_uuid(OriginalXml(cfdi_xml()))


def test_max_elements_is_enforced_during_streaming_parse() -> None:
    reader = SecureCfdiIdentityReader(max_elements=1)

    with pytest.raises(MalformedXml, match="structural safety limits"):
        reader.read_uuid(OriginalXml(cfdi_xml()))


def test_max_attribute_bytes_is_enforced_during_streaming_parse() -> None:
    reader = SecureCfdiIdentityReader(max_attribute_bytes=1)

    with pytest.raises(MalformedXml, match="attribute exceeds"):
        reader.read_uuid(OriginalXml(cfdi_xml()))


def test_case_d_raises_evidence_identity_mismatch(ingestion: IngestionFixture) -> None:
    use_case = ingestion.create_use_case()
    xml = cfdi_xml()
    digest = Sha256Digest.from_bytes(xml)
    other_identity = CfdiIdentity(
        uuid=CfdiUuid.from_raw("123E4567-E89B-42D3-A456-426614174000"),
        evidence=XmlEvidence.from_original_xml(OriginalXml(xml)),
    )
    ingestion.repository.identities_by_digest[digest] = other_identity

    with pytest.raises(EvidenceIdentityMismatch):
        use_case.ingest_cfdi_xml(xml)

    assert not ingestion.evidence_store.evidence_by_digest


def test_evidence_storage_failure_is_not_silently_wrapped() -> None:
    class FailingEvidenceStore:
        def store(self, evidence: XmlEvidence, extracted_uuid: CfdiUuid) -> None:
            raise EvidenceStorageFailure("simulated storage failure")

        def get_by_digest(self, digest: Sha256Digest) -> CfdiUuid | None:
            return None

    use_case = IngestCfdiXml(
        reader=SecureCfdiIdentityReader(),
        evidence_store=FailingEvidenceStore(),
        identity_repository=InMemoryIdentityRepository(),
        ingestion_records=InMemoryIngestionRecords(),
        unit_of_work=InMemoryUnitOfWork(),
    )

    with pytest.raises(EvidenceStorageFailure):
        use_case.ingest_cfdi_xml(cfdi_xml())

    def record_accepted(self, identity: CfdiIdentity, evidence: XmlEvidence) -> None:
        self.accepted.append((identity, evidence))
