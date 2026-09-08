from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from re import fullmatch
from uuid import RFC_4122, UUID

UUID_LEXICAL_PATTERN = (
    r"[a-f0-9A-F]{8}-[a-f0-9A-F]{4}-[a-f0-9A-F]{4}-[a-f0-9A-F]{4}-[a-f0-9A-F]{12}"
)


class CfdiIdentityError(Exception):
    """Base error for CFDI identity ingestion."""


class XmlInputTooLarge(CfdiIdentityError):
    """Raised when XML bytes exceed the configured safety limit."""


class MalformedXml(CfdiIdentityError):
    """Raised when XML is malformed or violates safety restrictions."""


class MissingTimbreFiscalDigital(CfdiIdentityError):
    """Raised when the exact SAT TimbreFiscalDigital element is absent."""


class MissingTimbreUuid(CfdiIdentityError):
    """Raised when the exact SAT TimbreFiscalDigital lacks UUID."""


class MultipleTimbreFiscalDigital(CfdiIdentityError):
    """Raised when more than one exact SAT TimbreFiscalDigital is present."""


class InvalidCfdiUuid(CfdiIdentityError):
    """Raised when a Timbre UUID is not a valid RFC 4122 UUID."""


class EvidenceIdentityMismatch(CfdiIdentityError):
    """Raised when one digest is already associated with another CFDI UUID."""


class EvidenceStorageFailure(CfdiIdentityError):
    """Raised when immutable evidence cannot be persisted."""


class IdentityPersistenceFailure(CfdiIdentityError):
    """Raised when identity metadata cannot be persisted."""


@dataclass(frozen=True, slots=True)
class CfdiUuid:
    value: str

    @classmethod
    def from_raw(cls, raw_value: str) -> CfdiUuid:
        try:
            normalized_value = raw_value.strip()
        except (AttributeError, ValueError) as error:
            raise InvalidCfdiUuid("TimbreFiscalDigital UUID is invalid") from error

        if len(normalized_value) != 36 or fullmatch(UUID_LEXICAL_PATTERN, normalized_value) is None:
            raise InvalidCfdiUuid("TimbreFiscalDigital UUID has an invalid lexical format")

        try:
            parsed = UUID(normalized_value)
        except ValueError as error:
            raise InvalidCfdiUuid("TimbreFiscalDigital UUID is invalid") from error

        if parsed.variant != RFC_4122:
            raise InvalidCfdiUuid("TimbreFiscalDigital UUID is not RFC 4122")

        return cls(str(parsed).upper())


@dataclass(frozen=True, slots=True)
class Sha256Digest:
    value: str

    def __post_init__(self) -> None:
        if len(self.value) != 64 or any(
            character not in "0123456789abcdef" for character in self.value
        ):
            raise ValueError("SHA-256 digest must be 64 lowercase hexadecimal characters")

    @classmethod
    def from_bytes(cls, content: bytes) -> Sha256Digest:
        return cls(sha256(content).hexdigest())


@dataclass(frozen=True, slots=True)
class OriginalXml:
    value: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.value, bytes) or not self.value:
            raise MalformedXml("XML input must not be empty")


@dataclass(frozen=True, slots=True)
class XmlEvidence:
    original_xml: OriginalXml
    sha256: Sha256Digest

    def __post_init__(self) -> None:
        if self.sha256 != Sha256Digest.from_bytes(self.original_xml.value):
            raise ValueError("SHA-256 digest must match the exact original XML bytes")

    @classmethod
    def from_original_xml(cls, original_xml: OriginalXml) -> XmlEvidence:
        return cls(original_xml=original_xml, sha256=Sha256Digest.from_bytes(original_xml.value))


@dataclass(frozen=True, slots=True)
class CfdiIdentity:
    uuid: CfdiUuid
    evidence: XmlEvidence


@dataclass(frozen=True, slots=True)
class IdentityConflict:
    existing_identity: CfdiIdentity
    incoming_evidence: XmlEvidence


class IngestionOutcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    REINGESTED = "REINGESTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


@dataclass(frozen=True, slots=True)
class IngestionResult:
    outcome: IngestionOutcome
    cfdi_identity: CfdiIdentity
    evidence: XmlEvidence

    @property
    def cfdi_uuid(self) -> CfdiUuid:
        return self.cfdi_identity.uuid

    @property
    def sha256(self) -> Sha256Digest:
        return self.evidence.sha256
