from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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
    Numeric,
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


class CfdiHeaderResultModel(Base):
    __tablename__ = "cfdi_header_result"
    __table_args__ = (
        Index("ix_cfdi_header_result_issuer_rfc", "issuer_rfc_canonical"),
        Index("ix_cfdi_header_result_receiver_rfc", "receiver_rfc_canonical"),
        Index("ix_cfdi_header_result_fecha", "fecha"),
        Index("ix_cfdi_header_result_tipo_comprobante", "tipo_comprobante"),
        UniqueConstraint("evidence_id", "parser_name", "parser_version", "configuration_hash"),
        UniqueConstraint("id", "evidence_id"),
        UniqueConstraint(
            "id", "evidence_id", "parser_name", "parser_version", "configuration_hash"
        ),
        ForeignKeyConstraint(["evidence_id"], ["xml_evidence.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["parser_name", "parser_version", "result_fingerprint_schema"],
            [
                "cfdi_header_parser_schema.parser_name",
                "cfdi_header_parser_schema.parser_version",
                "cfdi_header_parser_schema.result_fingerprint_schema",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("configuration_hash ~ '^[0-9a-f]{64}$'"),
        CheckConstraint("result_fingerprint ~ '^[0-9a-f]{64}$'"),
        CheckConstraint("issuer_rfc_canonical = upper(issuer_rfc_canonical)"),
        CheckConstraint("receiver_rfc_canonical = upper(receiver_rfc_canonical)"),
        CheckConstraint("(tipo_cambio_source IS NULL) = (tipo_cambio IS NULL)"),
        CheckConstraint("(descuento_source IS NULL) = (descuento IS NULL)"),
        CheckConstraint(
            "(cfdi_schema_version = '3.3' AND exportacion IS NULL "
            "AND domicilio_fiscal_receptor IS NULL AND regimen_fiscal_receptor IS NULL) "
            "OR (cfdi_schema_version = '4.0' AND exportacion IS NOT NULL "
            "AND issuer_nombre_source IS NOT NULL AND receiver_nombre_source IS NOT NULL "
            "AND domicilio_fiscal_receptor IS NOT NULL "
            "AND regimen_fiscal_receptor IS NOT NULL)"
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    evidence_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_fingerprint_schema: Mapped[str] = mapped_column(String(100), nullable=False)
    result_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    cfdi_schema_version: Mapped[str] = mapped_column(String(3), nullable=False)
    fecha_source: Mapped[str] = mapped_column(String, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    tipo_comprobante: Mapped[str] = mapped_column(String, nullable=False)
    serie_source: Mapped[str | None] = mapped_column(String)
    folio_source: Mapped[str | None] = mapped_column(String)
    moneda: Mapped[str] = mapped_column(String, nullable=False)
    tipo_cambio_source: Mapped[str | None] = mapped_column(String)
    tipo_cambio: Mapped[Decimal | None] = mapped_column(Numeric)
    subtotal_source: Mapped[str] = mapped_column(String, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    descuento_source: Mapped[str | None] = mapped_column(String)
    descuento: Mapped[Decimal | None] = mapped_column(Numeric)
    total_source: Mapped[str] = mapped_column(String, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    exportacion: Mapped[str | None] = mapped_column(String)
    lugar_expedicion: Mapped[str] = mapped_column(String, nullable=False)
    metodo_pago: Mapped[str | None] = mapped_column(String)
    forma_pago: Mapped[str | None] = mapped_column(String)
    condiciones_pago_source: Mapped[str | None] = mapped_column(String)
    confirmacion_source: Mapped[str | None] = mapped_column(String)
    issuer_rfc_source: Mapped[str] = mapped_column(String(32), nullable=False)
    issuer_rfc_canonical: Mapped[str] = mapped_column(String(32), nullable=False)
    issuer_nombre_source: Mapped[str | None] = mapped_column(String)
    issuer_regimen_fiscal: Mapped[str] = mapped_column(String, nullable=False)
    receiver_rfc_source: Mapped[str] = mapped_column(String(32), nullable=False)
    receiver_rfc_canonical: Mapped[str] = mapped_column(String(32), nullable=False)
    receiver_nombre_source: Mapped[str | None] = mapped_column(String)
    domicilio_fiscal_receptor: Mapped[str | None] = mapped_column(String)
    regimen_fiscal_receptor: Mapped[str | None] = mapped_column(String)
    uso_cfdi: Mapped[str] = mapped_column(String, nullable=False)


class CfdiHeaderParserSchemaModel(Base):
    __tablename__ = "cfdi_header_parser_schema"
    __table_args__ = (
        UniqueConstraint("parser_name", "parser_version"),
        UniqueConstraint("parser_name", "parser_version", "result_fingerprint_schema"),
        CheckConstraint("length(result_fingerprint_schema) > 0"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    result_fingerprint_schema: Mapped[str] = mapped_column(String(100), nullable=False)


class CfdiHeaderParseExecutionModel(Base):
    __tablename__ = "cfdi_header_parse_execution"
    __table_args__ = (
        Index("ix_cfdi_header_execution_evidence_parsed", "evidence_id", text("parsed_at DESC")),
        Index("ix_cfdi_header_execution_parser", "parser_name", "parser_version"),
        Index(
            "ix_cfdi_header_execution_failed",
            "parsed_at",
            postgresql_where=text("status = 'FAILED'"),
        ),
        ForeignKeyConstraint(["evidence_id"], ["xml_evidence.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["result_id", "evidence_id", "parser_name", "parser_version", "configuration_hash"],
            [
                "cfdi_header_result.id",
                "cfdi_header_result.evidence_id",
                "cfdi_header_result.parser_name",
                "cfdi_header_result.parser_version",
                "cfdi_header_result.configuration_hash",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('SUCCEEDED', 'FAILED')"),
        CheckConstraint("configuration_hash ~ '^[0-9a-f]{64}$'"),
        CheckConstraint(
            "(status = 'SUCCEEDED' AND result_id IS NOT NULL "
            "AND error_code IS NULL AND error_type IS NULL AND error_message IS NULL) "
            "OR (status = 'FAILED' AND result_id IS NULL "
            "AND error_code IS NOT NULL AND error_type IS NOT NULL)"
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    evidence_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result_id: Mapped[int | None] = mapped_column(BigInteger)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_type: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    implementation_id: Mapped[str | None] = mapped_column(String(100))
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CfdiHeaderCurrentModel(Base):
    __tablename__ = "cfdi_header_current"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cfdi_identity_id", "evidence_id"],
            ["cfdi_identity.id", "cfdi_identity.authoritative_evidence_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["result_id", "evidence_id"],
            ["cfdi_header_result.id", "cfdi_header_result.evidence_id"],
            ondelete="RESTRICT",
        ),
    )
    cfdi_identity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
