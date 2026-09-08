from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class XmlEvidenceModel(Base):
    __tablename__ = "xml_evidence"
    __table_args__ = (
        UniqueConstraint("sha256"),
        UniqueConstraint("id", "extracted_fiscal_uuid"),
        CheckConstraint("length(sha256) = 64"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'"),
        CheckConstraint("byte_length > 0"),
        CheckConstraint("byte_length = octet_length(content)"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_fiscal_uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CfdiIdentityModel(Base):
    __tablename__ = "cfdi_identity"
    __table_args__ = (
        UniqueConstraint("fiscal_uuid"),
        UniqueConstraint("authoritative_evidence_id"),
        UniqueConstraint("id", "fiscal_uuid"),
        UniqueConstraint("id", "authoritative_evidence_id"),
        ForeignKeyConstraint(
            ["authoritative_evidence_id", "fiscal_uuid"],
            ["xml_evidence.id", "xml_evidence.extracted_fiscal_uuid"],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    fiscal_uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    authoritative_evidence_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdentityConflictModel(Base):
    __tablename__ = "identity_conflict"
    __table_args__ = (
        UniqueConstraint("cfdi_identity_id", "incoming_evidence_id"),
        UniqueConstraint("id", "cfdi_identity_id", "incoming_evidence_id"),
        ForeignKeyConstraint(
            ["cfdi_identity_id", "fiscal_uuid"],
            ["cfdi_identity.id", "cfdi_identity.fiscal_uuid"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["incoming_evidence_id", "fiscal_uuid"],
            ["xml_evidence.id", "xml_evidence.extracted_fiscal_uuid"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("reviewed_at IS NULL OR reviewed_at >= first_seen_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    cfdi_identity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    incoming_evidence_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fiscal_uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class IngestionRecordModel(Base):
    __tablename__ = "ingestion_record"
    __table_args__ = (
        Index(
            "ix_ingestion_record_identity_received",
            "cfdi_identity_id",
            text("received_at DESC"),
        ),
        Index("ix_ingestion_record_evidence", "evidence_id"),
        Index("ix_ingestion_record_conflict", "identity_conflict_id"),
        ForeignKeyConstraint(["evidence_id"], ["xml_evidence.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["cfdi_identity_id"], ["cfdi_identity.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["cfdi_identity_id", "authoritative_evidence_id"],
            ["cfdi_identity.id", "cfdi_identity.authoritative_evidence_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["identity_conflict_id", "cfdi_identity_id", "evidence_id"],
            [
                "identity_conflict.id",
                "identity_conflict.cfdi_identity_id",
                "identity_conflict.incoming_evidence_id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("outcome IN ('ACCEPTED', 'REINGESTED', 'IDENTITY_CONFLICT')"),
        CheckConstraint(
            "(outcome IN ('ACCEPTED', 'REINGESTED') "
            "AND identity_conflict_id IS NULL "
            "AND evidence_id = authoritative_evidence_id) "
            "OR (outcome = 'IDENTITY_CONFLICT' "
            "AND identity_conflict_id IS NOT NULL "
            "AND evidence_id <> authoritative_evidence_id)"
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cfdi_identity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    authoritative_evidence_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    identity_conflict_id: Mapped[int | None] = mapped_column(BigInteger)
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_reference: Mapped[str | None] = mapped_column(String(255))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
