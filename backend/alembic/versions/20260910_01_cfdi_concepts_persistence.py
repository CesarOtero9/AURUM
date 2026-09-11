"""Frozen CFDI Concepts durable parsing persistence schema."""

import sqlalchemy as sa

from alembic import op

revision = "20260910_01"
down_revision = "20260909_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cfdi_concepts_parser_schema",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("parser_name", sa.String(100), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column("result_fingerprint_schema", sa.String(100), nullable=False),
        sa.UniqueConstraint("parser_name", "parser_version"),
        sa.UniqueConstraint("parser_name", "parser_version", "result_fingerprint_schema"),
        sa.CheckConstraint("length(result_fingerprint_schema) > 0"),
    )
    op.create_table(
        "cfdi_concepts_result",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("parser_name", sa.String(100), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("cfdi_version", sa.String(3), nullable=False),
        sa.Column("concept_count", sa.Integer(), nullable=False),
        sa.Column("result_fingerprint_schema", sa.String(100), nullable=False),
        sa.Column("result_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("evidence_id", "parser_name", "parser_version", "configuration_hash"),
        sa.UniqueConstraint("id", "evidence_id"),
        sa.UniqueConstraint(
            "id", "evidence_id", "parser_name", "parser_version", "configuration_hash"
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["xml_evidence.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["parser_name", "parser_version", "result_fingerprint_schema"],
            [
                "cfdi_concepts_parser_schema.parser_name",
                "cfdi_concepts_parser_schema.parser_version",
                "cfdi_concepts_parser_schema.result_fingerprint_schema",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("configuration_hash ~ '^[0-9a-f]{64}$'"),
        sa.CheckConstraint("result_fingerprint ~ '^[0-9a-f]{64}$'"),
        sa.CheckConstraint("cfdi_version IN ('3.3', '4.0')"),
        sa.CheckConstraint("concept_count > 0"),
    )
    op.create_table(
        "cfdi_concept",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("result_id", sa.BigInteger(), nullable=False),
        sa.Column("concept_index", sa.Integer(), nullable=False),
        sa.Column("clave_prod_serv_raw", sa.String(), nullable=False),
        sa.Column("no_identificacion_raw", sa.String()),
        sa.Column("cantidad_raw", sa.String(), nullable=False),
        sa.Column("cantidad", sa.Numeric(), nullable=False),
        sa.Column("clave_unidad_raw", sa.String(), nullable=False),
        sa.Column("unidad_raw", sa.String()),
        sa.Column("descripcion_raw", sa.Text(), nullable=False),
        sa.Column("valor_unitario_raw", sa.String(), nullable=False),
        sa.Column("valor_unitario", sa.Numeric(), nullable=False),
        sa.Column("importe_raw", sa.String(), nullable=False),
        sa.Column("importe", sa.Numeric(), nullable=False),
        sa.Column("descuento_raw", sa.String()),
        sa.Column("descuento", sa.Numeric()),
        sa.Column("objeto_imp_raw", sa.String()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("result_id", "concept_index"),
        sa.ForeignKeyConstraint(["result_id"], ["cfdi_concepts_result.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("concept_index >= 0"),
        sa.CheckConstraint("(descuento_raw IS NULL) = (descuento IS NULL)"),
    )
    op.create_table(
        "cfdi_concepts_parse_execution",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("parser_name", sa.String(100), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_id", sa.BigInteger()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_type", sa.String(200)),
        sa.Column("error_message", sa.Text()),
        sa.Column("implementation_id", sa.String(100)),
        sa.Column(
            "parsed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["xml_evidence.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["result_id", "evidence_id", "parser_name", "parser_version", "configuration_hash"],
            [
                "cfdi_concepts_result.id",
                "cfdi_concepts_result.evidence_id",
                "cfdi_concepts_result.parser_name",
                "cfdi_concepts_result.parser_version",
                "cfdi_concepts_result.configuration_hash",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("configuration_hash ~ '^[0-9a-f]{64}$'"),
        sa.CheckConstraint("status IN ('SUCCEEDED', 'FAILED')"),
        sa.CheckConstraint(
            "(status = 'SUCCEEDED' AND result_id IS NOT NULL "
            "AND error_code IS NULL AND error_type IS NULL AND error_message IS NULL) "
            "OR (status = 'FAILED' AND result_id IS NULL "
            "AND error_code IS NOT NULL AND error_type IS NOT NULL)"
        ),
    )
    op.create_index(
        "ix_cfdi_concepts_execution_evidence_parsed",
        "cfdi_concepts_parse_execution",
        ["evidence_id", sa.text("parsed_at DESC")],
    )
    op.create_index(
        "ix_cfdi_concepts_execution_parser",
        "cfdi_concepts_parse_execution",
        ["parser_name", "parser_version"],
    )
    op.create_index(
        "ix_cfdi_concepts_execution_failed",
        "cfdi_concepts_parse_execution",
        ["parsed_at"],
        postgresql_where=sa.text("status = 'FAILED'"),
    )
    op.create_table(
        "cfdi_concepts_current",
        sa.Column("cfdi_identity_id", sa.BigInteger(), primary_key=True),
        sa.Column("evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("result_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column(
            "promoted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cfdi_identity_id", "evidence_id"],
            ["cfdi_identity.id", "cfdi_identity.authoritative_evidence_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["result_id", "evidence_id"],
            ["cfdi_concepts_result.id", "cfdi_concepts_result.evidence_id"],
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("cfdi_concepts_current")
    op.drop_index("ix_cfdi_concepts_execution_failed", table_name="cfdi_concepts_parse_execution")
    op.drop_index("ix_cfdi_concepts_execution_parser", table_name="cfdi_concepts_parse_execution")
    op.drop_index(
        "ix_cfdi_concepts_execution_evidence_parsed", table_name="cfdi_concepts_parse_execution"
    )
    op.drop_table("cfdi_concepts_parse_execution")
    op.drop_table("cfdi_concept")
    op.drop_table("cfdi_concepts_result")
    op.drop_table("cfdi_concepts_parser_schema")
