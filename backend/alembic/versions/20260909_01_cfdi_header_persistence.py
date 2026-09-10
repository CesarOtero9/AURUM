"""Frozen CFDI Header durable parsing persistence schema."""

import sqlalchemy as sa

from alembic import op

revision = "20260909_01"
down_revision = "20260908_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cfdi_header_parser_schema",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("parser_name", sa.String(100), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column("result_fingerprint_schema", sa.String(100), nullable=False),
        sa.UniqueConstraint("parser_name", "parser_version"),
        sa.UniqueConstraint("parser_name", "parser_version", "result_fingerprint_schema"),
        sa.CheckConstraint("length(result_fingerprint_schema) > 0"),
    )
    op.create_table(
        "cfdi_header_result",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("parser_name", sa.String(100), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("result_fingerprint_schema", sa.String(100), nullable=False),
        sa.Column("result_fingerprint", sa.String(64), nullable=False),
        sa.Column("cfdi_schema_version", sa.String(3), nullable=False),
        sa.Column("fecha_source", sa.String(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=False), nullable=False),
        sa.Column("tipo_comprobante", sa.String(), nullable=False),
        sa.Column("serie_source", sa.String()),
        sa.Column("folio_source", sa.String()),
        sa.Column("moneda", sa.String(), nullable=False),
        sa.Column("tipo_cambio_source", sa.String()),
        sa.Column("tipo_cambio", sa.Numeric()),
        sa.Column("subtotal_source", sa.String(), nullable=False),
        sa.Column("subtotal", sa.Numeric(), nullable=False),
        sa.Column("descuento_source", sa.String()),
        sa.Column("descuento", sa.Numeric()),
        sa.Column("total_source", sa.String(), nullable=False),
        sa.Column("total", sa.Numeric(), nullable=False),
        sa.Column("exportacion", sa.String()),
        sa.Column("lugar_expedicion", sa.String(), nullable=False),
        sa.Column("metodo_pago", sa.String()),
        sa.Column("forma_pago", sa.String()),
        sa.Column("condiciones_pago_source", sa.String()),
        sa.Column("confirmacion_source", sa.String()),
        sa.Column("issuer_rfc_source", sa.String(32), nullable=False),
        sa.Column("issuer_rfc_canonical", sa.String(32), nullable=False),
        sa.Column("issuer_nombre_source", sa.String()),
        sa.Column("issuer_regimen_fiscal", sa.String(), nullable=False),
        sa.Column("receiver_rfc_source", sa.String(32), nullable=False),
        sa.Column("receiver_rfc_canonical", sa.String(32), nullable=False),
        sa.Column("receiver_nombre_source", sa.String()),
        sa.Column("domicilio_fiscal_receptor", sa.String()),
        sa.Column("regimen_fiscal_receptor", sa.String()),
        sa.Column("uso_cfdi", sa.String(), nullable=False),
        sa.UniqueConstraint("evidence_id", "parser_name", "parser_version", "configuration_hash"),
        sa.UniqueConstraint("id", "evidence_id"),
        sa.UniqueConstraint(
            "id", "evidence_id", "parser_name", "parser_version", "configuration_hash"
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["xml_evidence.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["parser_name", "parser_version", "result_fingerprint_schema"],
            [
                "cfdi_header_parser_schema.parser_name",
                "cfdi_header_parser_schema.parser_version",
                "cfdi_header_parser_schema.result_fingerprint_schema",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("configuration_hash ~ '^[0-9a-f]{64}$'"),
        sa.CheckConstraint("result_fingerprint ~ '^[0-9a-f]{64}$'"),
        sa.CheckConstraint("issuer_rfc_canonical = upper(issuer_rfc_canonical)"),
        sa.CheckConstraint("receiver_rfc_canonical = upper(receiver_rfc_canonical)"),
        sa.CheckConstraint("(tipo_cambio_source IS NULL) = (tipo_cambio IS NULL)"),
        sa.CheckConstraint("(descuento_source IS NULL) = (descuento IS NULL)"),
        sa.CheckConstraint(
            "(cfdi_schema_version = '3.3' AND exportacion IS NULL "
            "AND domicilio_fiscal_receptor IS NULL AND regimen_fiscal_receptor IS NULL) "
            "OR (cfdi_schema_version = '4.0' AND exportacion IS NOT NULL "
            "AND issuer_nombre_source IS NOT NULL AND receiver_nombre_source IS NOT NULL "
            "AND domicilio_fiscal_receptor IS NOT NULL "
            "AND regimen_fiscal_receptor IS NOT NULL)"
        ),
    )
    op.create_index(
        "ix_cfdi_header_result_issuer_rfc",
        "cfdi_header_result",
        ["issuer_rfc_canonical"],
    )
    op.create_index(
        "ix_cfdi_header_result_receiver_rfc",
        "cfdi_header_result",
        ["receiver_rfc_canonical"],
    )
    op.create_index("ix_cfdi_header_result_fecha", "cfdi_header_result", ["fecha"])
    op.create_index(
        "ix_cfdi_header_result_tipo_comprobante",
        "cfdi_header_result",
        ["tipo_comprobante"],
    )
    op.create_table(
        "cfdi_header_parse_execution",
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
                "cfdi_header_result.id",
                "cfdi_header_result.evidence_id",
                "cfdi_header_result.parser_name",
                "cfdi_header_result.parser_version",
                "cfdi_header_result.configuration_hash",
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
        "ix_cfdi_header_execution_evidence_parsed",
        "cfdi_header_parse_execution",
        ["evidence_id", sa.text("parsed_at DESC")],
    )
    op.create_index(
        "ix_cfdi_header_execution_parser",
        "cfdi_header_parse_execution",
        ["parser_name", "parser_version"],
    )
    op.create_index(
        "ix_cfdi_header_execution_failed",
        "cfdi_header_parse_execution",
        ["parsed_at"],
        postgresql_where=sa.text("status = 'FAILED'"),
    )
    op.create_table(
        "cfdi_header_current",
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
            ["cfdi_header_result.id", "cfdi_header_result.evidence_id"],
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("cfdi_header_current")
    op.drop_index("ix_cfdi_header_execution_failed", table_name="cfdi_header_parse_execution")
    op.drop_index("ix_cfdi_header_execution_parser", table_name="cfdi_header_parse_execution")
    op.drop_index(
        "ix_cfdi_header_execution_evidence_parsed", table_name="cfdi_header_parse_execution"
    )
    op.drop_table("cfdi_header_parse_execution")
    op.drop_index("ix_cfdi_header_result_tipo_comprobante", table_name="cfdi_header_result")
    op.drop_index("ix_cfdi_header_result_fecha", table_name="cfdi_header_result")
    op.drop_index("ix_cfdi_header_result_receiver_rfc", table_name="cfdi_header_result")
    op.drop_index("ix_cfdi_header_result_issuer_rfc", table_name="cfdi_header_result")
    op.drop_table("cfdi_header_result")
    op.drop_table("cfdi_header_parser_schema")
