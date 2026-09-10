"""PostgreSQL integration coverage for immutable CFDI Header persistence."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from threading import Barrier, Event

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from alembic import command
from aurum.domain.cfdi_header import (
    PARSER_NAME,
    PARSER_VERSION,
    DerivedResultDeterminismViolation,
    HeaderPromotionError,
    ParserFingerprintSchemaMismatch,
)
from aurum.domain.cfdi_identity import OriginalXml, XmlEvidence
from aurum.infrastructure.sqlalchemy_adapters import SqlAlchemyCfdiHeaderRepository
from aurum.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from aurum.infrastructure.xml_cfdi_header_reader import CfdiFiscalHeaderReader

TEST_DATABASE_URL = os.environ.get("AURUM_TEST_DATABASE_URL")
CONFIG_A = "a" * 64
CONFIG_B = "b" * 64
UUID_A = "039D171E-773B-495C-881F-BBEFBC8991C2"
UUID_B = "123E4567-E89B-42D3-A456-426614174000"
UUID_C = "223E4567-E89B-42D3-A456-426614174001"
SCHEMA_V1 = "cfdi-header-fingerprint/1"
SCHEMA_V2 = "cfdi-header-fingerprint/2"

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="AURUM_TEST_DATABASE_URL is not configured; real PostgreSQL is required",
)


def _url() -> str:
    assert TEST_DATABASE_URL is not None
    url = make_url(TEST_DATABASE_URL)
    if not url.drivername.startswith("postgresql") or not url.database:
        raise RuntimeError("AURUM_TEST_DATABASE_URL must name a PostgreSQL database")
    if "test" not in url.database.lower():
        raise RuntimeError("AURUM_TEST_DATABASE_URL database name must contain 'test'")
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="module")
def database_url() -> str:
    return _url()


@pytest.fixture(scope="module")
def migrated_database(database_url: str) -> str:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


@pytest.fixture(scope="module")
def migration_cycle_database(database_url: str) -> str:
    """Serialized migration-only fixture; it owns no normal CRUD engine/pool."""
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    try:
        yield database_url
    finally:
        command.upgrade(config, "head")


@pytest.fixture
def engine(migrated_database: str):
    database_engine = create_engine(migrated_database)
    with database_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE cfdi_header_current, cfdi_header_parse_execution, "
                "cfdi_header_result, cfdi_header_parser_schema, ingestion_record, "
                "identity_conflict, cfdi_identity, xml_evidence RESTART IDENTITY CASCADE"
            )
        )
    yield database_engine
    database_engine.dispose()


def _insert_evidence(connection, fiscal_uuid: str, suffix: bytes = b"") -> int:
    content = b"header-evidence:" + fiscal_uuid.encode() + suffix
    return int(
        connection.execute(
            text(
                "INSERT INTO xml_evidence (sha256, extracted_fiscal_uuid, content, byte_length) "
                "VALUES (:sha, :uuid, :content, :length) RETURNING id"
            ),
            {
                "sha": sha256(content).hexdigest(),
                "uuid": fiscal_uuid,
                "content": content,
                "length": len(content),
            },
        ).scalar_one()
    )


def _insert_identity(connection, evidence_id: int, fiscal_uuid: str) -> int:
    return int(
        connection.execute(
            text(
                "INSERT INTO cfdi_identity (fiscal_uuid, authoritative_evidence_id) "
                "VALUES (:uuid, :evidence) RETURNING id"
            ),
            {"uuid": fiscal_uuid, "evidence": evidence_id},
        ).scalar_one()
    )


def _authoritative_identity(connection, fiscal_uuid: str = UUID_A) -> tuple[int, int]:
    evidence_id = _insert_evidence(connection, fiscal_uuid)
    return _insert_identity(connection, evidence_id, fiscal_uuid), evidence_id


def _additional_evidence(connection, fiscal_uuid: str = UUID_B) -> int:
    return _insert_evidence(connection, fiscal_uuid)


def _header(version: str = "4.0"):
    root_extra = " Exportacion='01'" if version == "4.0" else ""
    issuer_name = " Nombre='Issuer'" if version == "4.0" else ""
    receiver_40 = (
        " Nombre='Receiver' DomicilioFiscalReceptor='01000' RegimenFiscalReceptor='601'"
        if version == "4.0"
        else ""
    )
    xml = (
        f"<cfdi:Comprobante xmlns:cfdi='http://www.sat.gob.mx/cfd/{version[0]}' "
        f"Version='{version}' Fecha='2024-01-01T12:30:00' TipoDeComprobante='I' "
        f"Moneda='MXN' TipoCambio='1.0000' SubTotal='100.00' Descuento='0.00' "
        f"Total='100.00' LugarExpedicion='01000' MetodoPago='PUE' FormaPago='03'"
        f"{root_extra}><cfdi:Emisor Rfc='AAA010101AAA'{issuer_name} "
        "RegimenFiscal='601'/><cfdi:Receptor Rfc='XAXX010101000' "
        f"UsoCFDI='G03'{receiver_40}/></cfdi:Comprobante>"
    ).encode()
    return CfdiFiscalHeaderReader().read(XmlEvidence.from_original_xml(OriginalXml(xml)))


def _factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


def _record_success(factory, evidence_id: int, header, configuration_hash: str = CONFIG_A) -> int:
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        return (
            SqlAlchemyCfdiHeaderRepository(uow)
            .record_success(evidence_id, header, configuration_hash)
            .id
        )


def _record_failure(factory, evidence_id: int) -> None:
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        SqlAlchemyCfdiHeaderRepository(uow).record_failure(
            evidence_id, CONFIG_A, ValueError("invalid source XML")
        )


def _row(evidence_id: int, *, version: str = "4.0", config: str = CONFIG_A) -> dict[str, object]:
    values: dict[str, object] = {
        "evidence_id": evidence_id,
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "configuration_hash": config,
        "result_fingerprint_schema": SCHEMA_V1,
        "result_fingerprint": "c" * 64,
        "cfdi_schema_version": version,
        "fecha_source": "2024-01-01T12:30:00",
        "fecha": datetime(2024, 1, 1, 12, 30),
        "tipo_comprobante": "I",
        "moneda": "MXN",
        "subtotal_source": "100.00",
        "subtotal": Decimal("100.00"),
        "total_source": "100.00",
        "total": Decimal("100.00"),
        "lugar_expedicion": "01000",
        "issuer_rfc_source": "AAA010101AAA",
        "issuer_rfc_canonical": "AAA010101AAA",
        "issuer_regimen_fiscal": "601",
        "receiver_rfc_source": "XAXX010101000",
        "receiver_rfc_canonical": "XAXX010101000",
        "uso_cfdi": "G03",
    }
    if version == "4.0":
        values.update(
            {
                "exportacion": "01",
                "issuer_nombre_source": "Issuer",
                "receiver_nombre_source": "Receiver",
                "domicilio_fiscal_receptor": "01000",
                "regimen_fiscal_receptor": "601",
            }
        )
    return values


def _insert_registry(connection, schema: str = SCHEMA_V1) -> None:
    connection.execute(
        text(
            "INSERT INTO cfdi_header_parser_schema "
            "(parser_name, parser_version, result_fingerprint_schema) "
            "VALUES (:name, :version, :schema)"
        ),
        {"name": PARSER_NAME, "version": PARSER_VERSION, "schema": schema},
    )


def _insert_result(connection, values: dict[str, object]) -> int:
    statement = text(
        "INSERT INTO cfdi_header_result ("
        + ", ".join(values)
        + ") VALUES ("
        + ", ".join(f":{key}" for key in values)
        + ") RETURNING id"
    )
    return int(connection.execute(statement, values).scalar_one())


def test_migration_creates_tables_and_indexes(migration_cycle_database: str) -> None:
    migration_engine = create_engine(migration_cycle_database)
    try:
        inspector = inspect(migration_engine)
        assert {
            "cfdi_header_parser_schema",
            "cfdi_header_result",
            "cfdi_header_parse_execution",
            "cfdi_header_current",
        } <= set(inspector.get_table_names())
        assert {
            "ix_cfdi_header_execution_evidence_parsed",
            "ix_cfdi_header_execution_parser",
            "ix_cfdi_header_execution_failed",
        } <= {index["name"] for index in inspector.get_indexes("cfdi_header_parse_execution")}
        assert {
            "ix_cfdi_header_result_issuer_rfc",
            "ix_cfdi_header_result_receiver_rfc",
            "ix_cfdi_header_result_fecha",
            "ix_cfdi_header_result_tipo_comprobante",
        } <= {index["name"] for index in inspector.get_indexes("cfdi_header_result")}
    finally:
        migration_engine.dispose()


def test_migration_can_downgrade_and_upgrade(migration_cycle_database: str) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", migration_cycle_database)
    # This test owns no pooled engine and always restores head before returning.
    try:
        command.downgrade(config, "20260908_01")
    finally:
        command.upgrade(config, "head")


def test_successful_persistence_round_trips(engine) -> None:
    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
    result_id = _record_success(_factory(engine), evidence_id, _header())
    with engine.connect() as connection:
        result = (
            connection.execute(
                text("SELECT * FROM cfdi_header_result WHERE id=:id"), {"id": result_id}
            )
            .mappings()
            .one()
        )
        assert result["subtotal"] == Decimal("100.00")
        assert result["fecha"].tzinfo is None
        assert result["result_fingerprint_schema"] == SCHEMA_V1
        assert len(result["result_fingerprint"]) == 64
        assert (
            connection.execute(text("SELECT count(*) FROM cfdi_header_parser_schema")).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM cfdi_header_parse_execution")
            ).scalar_one()
            == 1
        )


def test_identical_logical_result_reuses_result_and_appends_execution(engine) -> None:
    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
    factory = _factory(engine)
    first = _record_success(factory, evidence_id, _header())
    second = _record_success(factory, evidence_id, _header())
    assert first == second
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cfdi_header_result")).scalar_one() == 1
        assert (
            connection.execute(
                text("SELECT count(*) FROM cfdi_header_parse_execution")
            ).scalar_one()
            == 2
        )
        assert (
            connection.execute(text("SELECT count(*) FROM cfdi_header_parser_schema")).scalar_one()
            == 1
        )


def test_determinism_violation_preserves_outer_uow(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
    factory = _factory(engine)
    result_id = _record_success(factory, evidence_id, _header())
    monkeypatch.setattr(adapters, "fingerprint", lambda _: (SCHEMA_V1, "d" * 64))
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        repository = SqlAlchemyCfdiHeaderRepository(uow)
        with pytest.raises(DerivedResultDeterminismViolation):
            repository.record_success(evidence_id, _header(), CONFIG_A)
        repository.record_failure(evidence_id, CONFIG_B, ValueError("still usable"))
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cfdi_header_result")).scalar_one() == 1
        assert (
            connection.execute(
                text("SELECT count(*) FROM cfdi_header_parse_execution")
            ).scalar_one()
            == 2
        )
        assert (
            connection.execute(
                text("SELECT result_fingerprint FROM cfdi_header_result WHERE id=:id"),
                {"id": result_id},
            ).scalar_one()
            != "d" * 64
        )


def test_same_result_schema_mismatch_is_checked_before_digest(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
    factory = _factory(engine)
    _record_success(factory, evidence_id, _header())
    monkeypatch.setattr(adapters, "fingerprint", lambda _: (SCHEMA_V2, "d" * 64))
    with pytest.raises(ParserFingerprintSchemaMismatch):
        _record_success(factory, evidence_id, _header())
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cfdi_header_result")).scalar_one() == 1
        assert (
            connection.execute(
                text("SELECT count(*) FROM cfdi_header_parse_execution")
            ).scalar_one()
            == 1
        )


def test_global_parser_schema_mismatch_is_rejected(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_a = _additional_evidence(connection, UUID_A)
        evidence_b = _additional_evidence(connection, UUID_B)
    factory = _factory(engine)
    _record_success(factory, evidence_a, _header())
    monkeypatch.setattr(adapters, "fingerprint", lambda _: (SCHEMA_V2, "e" * 64))
    with pytest.raises(ParserFingerprintSchemaMismatch):
        _record_success(factory, evidence_b, _header())
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM cfdi_header_parser_schema")).scalar_one()
            == 1
        )


def test_failed_execution_has_no_result(engine) -> None:
    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
    _record_failure(_factory(engine), evidence_id)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM cfdi_header_parse_execution")).mappings().one()
        assert row["status"] == "FAILED" and row["result_id"] is None
        assert row["error_code"] == "ValueError" and row["error_message"] == "invalid source XML"
        assert connection.execute(text("SELECT count(*) FROM cfdi_header_result")).scalar_one() == 0


@pytest.mark.parametrize(
    "status,result_id,error_code,error_type,error_message,configuration_hash",
    [
        ("FAILED", 1, "E", "T", "message", CONFIG_A),
        ("SUCCEEDED", None, "E", None, None, CONFIG_A),
        ("SUCCEEDED", None, None, "T", None, CONFIG_A),
        ("SUCCEEDED", None, None, None, "message", CONFIG_A),
        ("FAILED", None, "E", "T", "message", "not-a-hash"),
    ],
)
def test_execution_shape_constraints(
    engine, status, result_id, error_code, error_type, error_message, configuration_hash
) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence_id = _additional_evidence(connection)
            if result_id is not None:
                _insert_registry(connection)
                result_id = _insert_result(connection, _row(evidence_id))
            connection.execute(
                text(
                    "INSERT INTO cfdi_header_parse_execution "
                    "(evidence_id, parser_name, parser_version, configuration_hash, status, "
                    "result_id, error_code, error_type, error_message) VALUES "
                    "(:evidence, :name, :version, :configuration_hash, :status, :result_id, "
                    ":error_code, :error_type, :error_message)"
                ),
                {
                    "evidence": evidence_id,
                    "name": PARSER_NAME,
                    "version": PARSER_VERSION,
                    "configuration_hash": configuration_hash,
                    "status": status,
                    "result_id": result_id,
                    "error_code": error_code,
                    "error_type": error_type,
                    "error_message": error_message,
                },
            )


@pytest.mark.parametrize(
    "version,field,value",
    [
        ("3.3", "exportacion", "01"),
        ("3.3", "domicilio_fiscal_receptor", "01000"),
        ("3.3", "regimen_fiscal_receptor", "601"),
        ("4.0", "exportacion", None),
        ("4.0", "issuer_nombre_source", None),
        ("4.0", "receiver_nombre_source", None),
        ("4.0", "domicilio_fiscal_receptor", None),
        ("4.0", "regimen_fiscal_receptor", None),
    ],
)
def test_version_matrix_constraints(engine, version, field, value) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence_id = _additional_evidence(connection)
            _insert_registry(connection)
            _insert_result(connection, _row(evidence_id, version=version) | {field: value})


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_version_matrix_accepts_valid_rows(engine, version) -> None:
    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
        _insert_registry(connection)
        _insert_result(connection, _row(evidence_id, version=version))


@pytest.mark.parametrize(
    "field,value",
    [
        ("tipo_cambio_source", "1.0000"),
        ("tipo_cambio", Decimal("1.0000")),
        ("descuento_source", "0.00"),
        ("descuento", Decimal("0.00")),
    ],
)
def test_source_parsed_pair_constraints(engine, field, value) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence_id = _additional_evidence(connection)
            _insert_registry(connection)
            _insert_result(connection, _row(evidence_id) | {field: value})


def test_source_parsed_pairs_accept_null_and_populated(engine) -> None:
    with engine.begin() as connection:
        first = _additional_evidence(connection, UUID_A)
        second = _additional_evidence(connection, UUID_B)
        _insert_registry(connection)
        _insert_result(connection, _row(first))
        _insert_result(
            connection,
            _row(second, config=CONFIG_B)
            | {
                "tipo_cambio_source": "1.0000",
                "tipo_cambio": Decimal("1.0000"),
                "descuento_source": "0.00",
                "descuento": Decimal("0.00"),
            },
        )


@pytest.mark.parametrize("field", ["issuer_rfc_canonical", "receiver_rfc_canonical"])
def test_rfc_canonical_must_be_uppercase(engine, field) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence_id = _additional_evidence(connection)
            _insert_registry(connection)
            _insert_result(connection, _row(evidence_id) | {field: "aaa010101aaa"})


def test_rfc_canonical_accepts_uppercase(engine) -> None:
    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
        _insert_registry(connection)
        _insert_result(connection, _row(evidence_id))


def test_execution_composite_provenance_fk(engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence_a = _additional_evidence(connection, UUID_A)
            evidence_b = _additional_evidence(connection, UUID_B)
            _insert_registry(connection)
            result_a = _insert_result(connection, _row(evidence_a))
            _insert_result(connection, _row(evidence_b, config=CONFIG_B))
            connection.execute(
                text(
                    "INSERT INTO cfdi_header_parse_execution "
                    "(evidence_id, parser_name, parser_version, configuration_hash, "
                    "status, result_id) "
                    "VALUES (:evidence, :name, :version, :configuration, 'SUCCEEDED', :result)"
                ),
                {
                    "evidence": evidence_b,
                    "name": PARSER_NAME,
                    "version": PARSER_VERSION,
                    "configuration": CONFIG_B,
                    "result": result_a,
                },
            )


def test_current_promotion_and_explicit_replacement(engine) -> None:
    with engine.begin() as connection:
        identity_id, evidence_id = _authoritative_identity(connection)
    factory = _factory(engine)
    first = _record_success(factory, evidence_id, _header(), CONFIG_A)
    second = _record_success(factory, evidence_id, _header(), CONFIG_B)
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, first)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT result_id FROM cfdi_header_current")).scalar_one()
            == first
        )
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, second)
    with engine.connect() as connection:
        current = connection.execute(text("SELECT * FROM cfdi_header_current")).mappings().one()
        assert current["result_id"] == second and current["promoted_at"] is not None
        assert connection.execute(text("SELECT count(*) FROM cfdi_header_result")).scalar_one() == 2
        assert (
            connection.execute(
                text("SELECT count(*) FROM cfdi_header_parse_execution")
            ).scalar_one()
            == 2
        )


def test_current_rejects_real_non_authoritative_result(engine) -> None:
    with engine.begin() as connection:
        identity_id, authoritative = _authoritative_identity(connection, UUID_A)
        other_evidence = _additional_evidence(connection, UUID_B)
    factory = _factory(engine)
    authorized = _record_success(factory, authoritative, _header(), CONFIG_A)
    foreign = _record_success(factory, other_evidence, _header(), CONFIG_B)
    uow = SqlAlchemyUnitOfWork(factory)
    with pytest.raises(HeaderPromotionError):
        with uow:
            SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, foreign)
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, authorized)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT result_id FROM cfdi_header_current")).scalar_one()
            == authorized
        )


def test_current_direct_constraints(engine) -> None:
    with engine.begin() as connection:
        identity_id, evidence_a = _authoritative_identity(connection, UUID_A)
        evidence_b = _additional_evidence(connection, UUID_B)
        _insert_registry(connection)
        result_a = _insert_result(connection, _row(evidence_a))
        result_b = _insert_result(connection, _row(evidence_b, config=CONFIG_B))
        connection.execute(
            text(
                "INSERT INTO cfdi_header_current "
                "(cfdi_identity_id, evidence_id, result_id) VALUES (:identity,:evidence,:result)"
            ),
            {"identity": identity_id, "evidence": evidence_a, "result": result_a},
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO cfdi_header_current "
                    "(cfdi_identity_id, evidence_id, result_id) "
                    "VALUES (:identity,:evidence,:result)"
                ),
                {"identity": identity_id, "evidence": evidence_b, "result": result_b},
            )


def test_current_result_id_is_unique(engine) -> None:
    constraints = inspect(engine).get_unique_constraints("cfdi_header_current")
    assert any(constraint["column_names"] == ["result_id"] for constraint in constraints)


def test_current_rejects_result_from_other_evidence_directly(engine) -> None:
    with engine.begin() as connection:
        identity_id, evidence_a = _authoritative_identity(connection, UUID_A)
        evidence_b = _additional_evidence(connection, UUID_B)
        _insert_registry(connection)
        _insert_result(connection, _row(evidence_a))
        foreign_result = _insert_result(connection, _row(evidence_b, config=CONFIG_B))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO cfdi_header_current "
                    "(cfdi_identity_id, evidence_id, result_id) "
                    "VALUES (:identity,:evidence,:result)"
                ),
                {
                    "identity": identity_id,
                    "evidence": evidence_a,
                    "result": foreign_result,
                },
            )


def test_invalid_promotion_preserves_existing_current(engine) -> None:
    with engine.begin() as connection:
        identity_id, evidence_a = _authoritative_identity(connection, UUID_A)
        evidence_b = _additional_evidence(connection, UUID_B)
    factory = _factory(engine)
    result_a = _record_success(factory, evidence_a, _header(), CONFIG_A)
    result_b = _record_success(factory, evidence_b, _header(), CONFIG_B)
    with SqlAlchemyUnitOfWork(factory) as uow:
        SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, result_a)
    with pytest.raises(HeaderPromotionError):
        with SqlAlchemyUnitOfWork(factory) as uow:
            SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, result_b)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT result_id FROM cfdi_header_current")) == result_a
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_result")) == 2
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_parse_execution")) == 2


def test_failed_execution_preserves_current(engine) -> None:
    with engine.begin() as connection:
        identity_id, evidence_id = _authoritative_identity(connection)
    factory = _factory(engine)
    result_id = _record_success(factory, evidence_id, _header())
    with SqlAlchemyUnitOfWork(factory) as uow:
        SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, result_id)
    _record_failure(factory, evidence_id)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT result_id FROM cfdi_header_current")) == result_id
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_parse_execution")) == 2


def test_repository_keeps_existing_result_immutable(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
    factory = _factory(engine)
    result_id = _record_success(factory, evidence_id, _header())
    with engine.connect() as connection:
        original = connection.execute(
            text(
                "SELECT subtotal, total, result_fingerprint, evidence_id, configuration_hash "
                "FROM cfdi_header_result WHERE id=:id"
            ),
            {"id": result_id},
        ).one()
    _record_success(factory, evidence_id, _header())
    monkeypatch.setattr(adapters, "fingerprint", lambda _: (SCHEMA_V1, "d" * 64))
    with pytest.raises(DerivedResultDeterminismViolation):
        _record_success(factory, evidence_id, _header())
    monkeypatch.setattr(adapters, "fingerprint", lambda _: (SCHEMA_V2, "e" * 64))
    with pytest.raises(ParserFingerprintSchemaMismatch):
        _record_success(factory, evidence_id, _header())
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT subtotal, total, result_fingerprint, evidence_id, configuration_hash "
                    "FROM cfdi_header_result WHERE id=:id"
                ),
                {"id": result_id},
            ).one()
            == original
        )


def test_restrict_delete_preserves_provenance_history(engine) -> None:
    with engine.begin() as connection:
        identity_id, evidence_id = _authoritative_identity(connection)
    factory = _factory(engine)
    result_id = _record_success(factory, evidence_id, _header())
    with SqlAlchemyUnitOfWork(factory) as uow:
        SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, result_id)
    for statement, identifier in (
        ("DELETE FROM xml_evidence WHERE id=:id", evidence_id),
        ("DELETE FROM cfdi_header_result WHERE id=:id", result_id),
        ("DELETE FROM cfdi_identity WHERE id=:id", identity_id),
    ):
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text(statement), {"id": identifier})


def test_failed_execution_without_message_is_accepted(engine) -> None:
    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
        connection.execute(
            text(
                "INSERT INTO cfdi_header_parse_execution "
                "(evidence_id, parser_name, parser_version, configuration_hash, status, "
                "error_code, error_type) VALUES (:evidence,:name,:version,:configuration,"
                "'FAILED','E','T')"
            ),
            {
                "evidence": evidence_id,
                "name": PARSER_NAME,
                "version": PARSER_VERSION,
                "configuration": CONFIG_A,
            },
        )


def test_deterministic_result_registration_race(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
        _insert_registry(connection)
    reached = Barrier(2)
    monkeypatch.setattr(adapters, "_after_missing_header_result", reached.wait)
    factory = _factory(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result_ids = list(
            pool.map(lambda _: _record_success(factory, evidence_id, _header()), range(2))
        )
    assert result_ids[0] == result_ids[1]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_parse_execution")) == 2


def test_deterministic_registry_registration_race(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _additional_evidence(connection)
    reached = Barrier(2)
    monkeypatch.setattr(adapters, "_after_missing_parser_schema", reached.wait)
    factory = _factory(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result_ids = list(
            pool.map(lambda _: _record_success(factory, evidence_id, _header()), range(2))
        )
    assert result_ids[0] == result_ids[1]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_parser_schema")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_parse_execution")) == 2


def test_concurrent_promotions_are_serialized(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        identity_id, evidence_id = _authoritative_identity(connection)
    factory = _factory(engine)
    first = _record_success(factory, evidence_id, _header(), CONFIG_A)
    second = _record_success(factory, evidence_id, _header(), CONFIG_B)
    first_locked, release_first = Event(), Event()

    def hold_first_lock() -> None:
        first_locked.set()
        release_first.wait()

    monkeypatch.setattr(adapters, "_after_identity_locked", hold_first_lock)

    def promote(result_id: int) -> None:
        with SqlAlchemyUnitOfWork(factory) as uow:
            SqlAlchemyCfdiHeaderRepository(uow).promote(identity_id, result_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(promote, first)
        assert first_locked.wait(timeout=5)
        second_future = pool.submit(promote, second)
        release_first.set()
        first_future.result()
        second_future.result()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_header_current")) == 1
        assert connection.scalar(text("SELECT result_id FROM cfdi_header_current")) == second
