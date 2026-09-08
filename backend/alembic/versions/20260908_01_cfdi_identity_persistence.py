"""CFDI identity immutable evidence persistence.

Revision ID: 20260908_01
Revises:
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260908_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "xml_evidence",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("extracted_fiscal_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", postgresql.BYTEA(), nullable=False),
        sa.Column("byte_length", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("sha256"), sa.UniqueConstraint("id", "extracted_fiscal_uuid"),
        sa.CheckConstraint("length(sha256) = 64"), sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'"),
        sa.CheckConstraint("byte_length > 0"), sa.CheckConstraint("byte_length = octet_length(content)"),
    )
    op.create_table(
        "cfdi_identity",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("fiscal_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authoritative_evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("fiscal_uuid"), sa.UniqueConstraint("authoritative_evidence_id"),
        sa.UniqueConstraint("id", "fiscal_uuid"), sa.UniqueConstraint("id", "authoritative_evidence_id"),
        sa.ForeignKeyConstraint(["authoritative_evidence_id", "fiscal_uuid"], ["xml_evidence.id", "xml_evidence.extracted_fiscal_uuid"], ondelete="RESTRICT"),
    )
    op.create_table(
        "identity_conflict",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("cfdi_identity_id", sa.BigInteger(), nullable=False),
        sa.Column("incoming_evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)), sa.Column("review_note", sa.Text()),
        sa.UniqueConstraint("cfdi_identity_id", "incoming_evidence_id"), sa.UniqueConstraint("id", "cfdi_identity_id", "incoming_evidence_id"),
        sa.ForeignKeyConstraint(["cfdi_identity_id", "fiscal_uuid"], ["cfdi_identity.id", "cfdi_identity.fiscal_uuid"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["incoming_evidence_id", "fiscal_uuid"], ["xml_evidence.id", "xml_evidence.extracted_fiscal_uuid"], ondelete="RESTRICT"),
        sa.CheckConstraint("reviewed_at IS NULL OR reviewed_at >= first_seen_at"),
    )
    op.create_table(
        "ingestion_record",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("outcome", sa.String(32), nullable=False), sa.Column("evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("cfdi_identity_id", sa.BigInteger(), nullable=False), sa.Column("authoritative_evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("identity_conflict_id", sa.BigInteger()), sa.Column("source_type", sa.String(32)), sa.Column("source_reference", sa.String(255)),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["evidence_id"], ["xml_evidence.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["cfdi_identity_id"], ["cfdi_identity.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cfdi_identity_id", "authoritative_evidence_id"], ["cfdi_identity.id", "cfdi_identity.authoritative_evidence_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["identity_conflict_id", "cfdi_identity_id", "evidence_id"], ["identity_conflict.id", "identity_conflict.cfdi_identity_id", "identity_conflict.incoming_evidence_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("outcome IN ('ACCEPTED', 'REINGESTED', 'IDENTITY_CONFLICT')"),
        sa.CheckConstraint("(outcome IN ('ACCEPTED', 'REINGESTED') AND identity_conflict_id IS NULL AND evidence_id = authoritative_evidence_id) OR (outcome = 'IDENTITY_CONFLICT' AND identity_conflict_id IS NOT NULL AND evidence_id <> authoritative_evidence_id)"),
    )
    op.create_index("ix_ingestion_record_identity_received", "ingestion_record", ["cfdi_identity_id", sa.text("received_at DESC")])
    op.create_index("ix_ingestion_record_evidence", "ingestion_record", ["evidence_id"])
    op.create_index("ix_ingestion_record_conflict", "ingestion_record", ["identity_conflict_id"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_record_conflict", table_name="ingestion_record")
    op.drop_index("ix_ingestion_record_evidence", table_name="ingestion_record")
    op.drop_index("ix_ingestion_record_identity_received", table_name="ingestion_record")
    op.drop_table("ingestion_record")
    op.drop_table("identity_conflict")
    op.drop_table("cfdi_identity")
    op.drop_table("xml_evidence")
