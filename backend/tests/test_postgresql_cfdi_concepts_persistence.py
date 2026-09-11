"""PostgreSQL integration coverage for immutable CFDI Concepts persistence."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
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
from aurum.domain.cfdi_concepts import (
    FINGERPRINT_SCHEMA,
    PARSER_NAME,
    PARSER_VERSION,
)
from aurum.domain.cfdi_header import (
    DerivedResultDeterminismViolation,
    HeaderPromotionError,
    ParserFingerprintSchemaMismatch,
)
from aurum.domain.cfdi_identity import OriginalXml, XmlEvidence
from aurum.infrastructure.sqlalchemy_adapters import SqlAlchemyCfdiConceptsRepository
from aurum.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from aurum.infrastructure.xml_cfdi_concepts_reader import CfdiConceptsReader

TEST_DATABASE_URL = os.environ.get("AURUM_TEST_DATABASE_URL")
CONFIG_A = "a" * 64
CONFIG_B = "b" * 64
UUID_A = "039D171E-773B-495C-881F-BBEFBC8991C2"
UUID_B = "123E4567-E89B-42D3-A456-426614174000"
UUID_C = "223E4567-E89B-42D3-A456-426614174001"
SCHEMA_V2 = "cfdi-concepts-fingerprint/2"

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="AURUM_TEST_DATABASE_URL is not configured; real PostgreSQL is required",
)


def _url() -> str:
    assert TEST_DATABASE_URL is not None
    url = make_url(TEST_DATABASE_URL)
    if not url.drivername.startswith("postgresql") or not url.database:
        raise RuntimeError("AURUM_TEST_DATABASE_URL must name PostgreSQL")
    if "test" not in url.database.lower():
        raise RuntimeError("AURUM_TEST_DATABASE_URL database name must contain test")
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
    value = create_engine(migrated_database)
    with value.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE cfdi_concepts_current, cfdi_concepts_parse_execution, "
                "cfdi_concept, cfdi_concepts_result, cfdi_concepts_parser_schema, "
                "xml_evidence RESTART IDENTITY CASCADE"
            )
        )
    yield value
    value.dispose()


def _evidence(connection, fiscal_uuid: str = UUID_A) -> int:
    content = f"concepts:{fiscal_uuid}".encode()
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


def _identity(connection, evidence_id: int, fiscal_uuid: str = UUID_A) -> int:
    return int(
        connection.execute(
            text(
                "INSERT INTO cfdi_identity (fiscal_uuid, authoritative_evidence_id) "
                "VALUES (:uuid, :evidence) RETURNING id"
            ),
            {"uuid": fiscal_uuid, "evidence": evidence_id},
        ).scalar_one()
    )


def _concepts(version: str = "4.0", multiple: bool = False):
    objeto = " ObjetoImp='02'" if version == "4.0" else ""
    one = (
        "<cfdi:Concepto ClaveProdServ='01010101' Cantidad='1.0000' "
        "ClaveUnidad='H87' Descripcion='Same' ValorUnitario='100.00' "
        f"Importe='100.0000' Descuento='0'{objeto}/>"
    )
    children = one + one if multiple else one
    xml = (
        f"<cfdi:Comprobante xmlns:cfdi='http://www.sat.gob.mx/cfd/{version[0]}' "
        f"Version='{version}'><cfdi:Conceptos>{children}</cfdi:Conceptos>"
        "</cfdi:Comprobante>"
    ).encode()
    return CfdiConceptsReader().read(XmlEvidence.from_original_xml(OriginalXml(xml)))


def _record(factory, evidence_id: int, concepts, config: str = CONFIG_A) -> int:
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        return (
            SqlAlchemyCfdiConceptsRepository(uow).record_success(evidence_id, concepts, config).id
        )


def _insert_registry(connection, schema: str = FINGERPRINT_SCHEMA) -> None:
    connection.execute(
        text(
            "INSERT INTO cfdi_concepts_parser_schema "
            "(parser_name, parser_version, result_fingerprint_schema) "
            "VALUES (:name, :version, :schema)"
        ),
        {"name": PARSER_NAME, "version": PARSER_VERSION, "schema": schema},
    )


def _result_values(
    evidence_id: int,
    *,
    config: str = CONFIG_A,
    version: str = "4.0",
    count: int = 1,
    fingerprint: str = "c" * 64,
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "configuration_hash": config,
        "cfdi_version": version,
        "concept_count": count,
        "result_fingerprint_schema": FINGERPRINT_SCHEMA,
        "result_fingerprint": fingerprint,
    }


def _insert_result(connection, values: dict[str, object]) -> int:
    return int(
        connection.execute(
            text(
                "INSERT INTO cfdi_concepts_result ("
                + ", ".join(values)
                + ") VALUES ("
                + ", ".join(f":{key}" for key in values)
                + ") RETURNING id"
            ),
            values,
        ).scalar_one()
    )


def _child_values(result_id: int, index: int = 0) -> dict[str, object]:
    return {
        "result_id": result_id,
        "concept_index": index,
        "clave_prod_serv_raw": "01010101",
        "cantidad_raw": "1.0000",
        "cantidad": Decimal("1.0000"),
        "clave_unidad_raw": "H87",
        "descripcion_raw": "Same",
        "valor_unitario_raw": "100.00",
        "valor_unitario": Decimal("100.00"),
        "importe_raw": "100.0000",
        "importe": Decimal("100.0000"),
        "descuento_raw": "0",
        "descuento": Decimal("0"),
        "objeto_imp_raw": "02",
    }


def _insert_child(connection, values: dict[str, object]) -> int:
    return int(
        connection.execute(
            text(
                "INSERT INTO cfdi_concept ("
                + ", ".join(values)
                + ") VALUES ("
                + ", ".join(f":{key}" for key in values)
                + ") RETURNING id"
            ),
            values,
        ).scalar_one()
    )


def test_migration_creates_concepts_schema(engine) -> None:
    names = set(inspect(engine).get_table_names())
    assert {
        "cfdi_concepts_parser_schema",
        "cfdi_concepts_result",
        "cfdi_concept",
        "cfdi_concepts_parse_execution",
        "cfdi_concepts_current",
    } <= names
    indexes = {
        item["name"] for item in inspect(engine).get_indexes("cfdi_concepts_parse_execution")
    }
    assert {
        "ix_cfdi_concepts_execution_evidence_parsed",
        "ix_cfdi_concepts_execution_parser",
        "ix_cfdi_concepts_execution_failed",
    } <= indexes


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_persists_order_raw_decimal_and_duplicate_children(engine, version: str) -> None:
    with engine.begin() as connection:
        evidence_id = _evidence(connection)
    result_id = _record(
        sessionmaker(engine, expire_on_commit=False), evidence_id, _concepts(version, True)
    )
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT concept_count, cfdi_version FROM cfdi_concepts_result WHERE id = :id"),
            {"id": result_id},
        ).one()
        children = connection.execute(
            text(
                "SELECT concept_index, cantidad_raw, cantidad, descuento_raw, descuento, "
                "objeto_imp_raw "
                "FROM cfdi_concept WHERE result_id = :id ORDER BY concept_index"
            ),
            {"id": result_id},
        ).all()
    assert result == (2, version)
    assert [row[0] for row in children] == [0, 1]
    assert children[0][1:5] == ("1.0000", 1, "0", 0)
    assert children[0][5] is None if version == "3.3" else children[0][5] == "02"


def test_idempotency_failure_and_current_projection(engine) -> None:
    with engine.begin() as connection:
        evidence_id = _evidence(connection)
        identity_id = _identity(connection, evidence_id)
    factory = sessionmaker(engine, expire_on_commit=False)
    parsed = _concepts()
    first = _record(factory, evidence_id, parsed)
    assert _record(factory, evidence_id, parsed) == first
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        repository = SqlAlchemyCfdiConceptsRepository(uow)
        repository.promote(identity_id, first)
        repository.record_failure(evidence_id, CONFIG_B, ValueError("bad concepts"))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concept")) == 1
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM cfdi_concepts_parse_execution WHERE status = 'SUCCEEDED'"
                )
            )
            == 2
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM cfdi_concepts_parse_execution WHERE status = 'FAILED'")
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT result_id FROM cfdi_concepts_current WHERE cfdi_identity_id = :id"),
                {"id": identity_id},
            )
            == first
        )


def test_reprocessing_and_non_authoritative_promotion_are_safe(engine) -> None:
    with engine.begin() as connection:
        evidence_a = _evidence(connection, UUID_A)
        identity_id = _identity(connection, evidence_a)
        evidence_b = _evidence(connection, UUID_B)
    factory = sessionmaker(engine, expire_on_commit=False)
    first = _record(factory, evidence_a, _concepts(), CONFIG_A)
    second = _record(factory, evidence_a, _concepts(), CONFIG_B)
    other = _record(factory, evidence_b, _concepts(), CONFIG_A)
    assert first != second
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        repository = SqlAlchemyCfdiConceptsRepository(uow)
        repository.promote(identity_id, first)
        with pytest.raises(HeaderPromotionError):
            repository.promote(identity_id, other)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 3
        assert (
            connection.scalar(
                text("SELECT result_id FROM cfdi_concepts_current WHERE cfdi_identity_id = :id"),
                {"id": identity_id},
            )
            == first
        )


def test_migration_exposes_critical_concepts_structures(
    migration_cycle_database: str,
) -> None:
    migration_engine = create_engine(migration_cycle_database)
    try:
        inspector = inspect(migration_engine)
        assert {
            "cfdi_concepts_parser_schema",
            "cfdi_concepts_result",
            "cfdi_concept",
            "cfdi_concepts_parse_execution",
            "cfdi_concepts_current",
        } <= set(inspector.get_table_names())
        assert any(
            item["column_names"] == ["result_id", "concept_index"]
            for item in inspector.get_unique_constraints("cfdi_concept")
        )
        assert any(
            item["column_names"]
            == ["evidence_id", "parser_name", "parser_version", "configuration_hash"]
            for item in inspector.get_unique_constraints("cfdi_concepts_result")
        )
        assert any(
            item["column_names"] == ["result_id"]
            for item in inspector.get_unique_constraints("cfdi_concepts_current")
        )
        assert {
            "ix_cfdi_concepts_execution_evidence_parsed",
            "ix_cfdi_concepts_execution_parser",
            "ix_cfdi_concepts_execution_failed",
        } <= {item["name"] for item in inspector.get_indexes("cfdi_concepts_parse_execution")}
    finally:
        migration_engine.dispose()


def test_migration_can_downgrade_and_upgrade(migration_cycle_database: str) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", migration_cycle_database)
    try:
        command.downgrade(config, "20260909_01")
        migration_engine = create_engine(migration_cycle_database)
        try:
            assert not {
                "cfdi_concepts_parser_schema",
                "cfdi_concepts_result",
                "cfdi_concept",
                "cfdi_concepts_parse_execution",
                "cfdi_concepts_current",
            } & set(inspect(migration_engine).get_table_names())
        finally:
            migration_engine.dispose()
    finally:
        command.upgrade(config, "20260910_01")


@pytest.mark.parametrize(
    "target, change",
    [
        ("child", {"concept_index": -1}),
        ("child", {"descuento_raw": None}),
        ("child", {"descuento": None}),
        ("result", {"concept_count": 0}),
        ("result", {"cfdi_version": "5.0"}),
        ("result", {"configuration_hash": "not-a-hash"}),
        ("result", {"result_fingerprint": "A" * 64}),
    ],
)
def test_direct_result_and_child_constraints(
    engine, target: str, change: dict[str, object]
) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence_id = _evidence(connection)
            _insert_registry(connection)
            values = _result_values(evidence_id)
            if target == "result":
                _insert_result(connection, values | change)
            else:
                result_id = _insert_result(connection, values)
                _insert_child(connection, _child_values(result_id) | change)


def test_direct_duplicate_child_index_constraint(engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence_id = _evidence(connection)
            _insert_registry(connection)
            result_id = _insert_result(connection, _result_values(evidence_id))
            _insert_child(connection, _child_values(result_id))
            _insert_child(connection, _child_values(result_id))


@pytest.mark.parametrize(
    "status, result_present, error_code, error_type, error_message, configuration",
    [
        ("SUCCEEDED", False, None, None, None, CONFIG_A),
        ("SUCCEEDED", True, "E", None, None, CONFIG_A),
        ("SUCCEEDED", True, None, "T", None, CONFIG_A),
        ("SUCCEEDED", True, None, None, "message", CONFIG_A),
        ("FAILED", True, "E", "T", "message", CONFIG_A),
        ("FAILED", False, "E", "T", "message", "not-a-hash"),
    ],
)
def test_direct_execution_shape_constraints(
    engine,
    status: str,
    result_present: bool,
    error_code: str | None,
    error_type: str | None,
    error_message: str | None,
    configuration: str,
) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence_id = _evidence(connection)
            result_id = None
            if result_present:
                _insert_registry(connection)
                result_id = _insert_result(connection, _result_values(evidence_id))
            connection.execute(
                text(
                    "INSERT INTO cfdi_concepts_parse_execution "
                    "(evidence_id, parser_name, parser_version, configuration_hash, status, "
                    "result_id, error_code, error_type, error_message) VALUES "
                    "(:evidence, :name, :version, :configuration, :status, :result, "
                    ":error_code, :error_type, :error_message)"
                ),
                {
                    "evidence": evidence_id,
                    "name": PARSER_NAME,
                    "version": PARSER_VERSION,
                    "configuration": configuration,
                    "status": status,
                    "result": result_id,
                    "error_code": error_code,
                    "error_type": error_type,
                    "error_message": error_message,
                },
            )


def test_repository_rejects_determinism_violation_without_mutating_result(
    engine, monkeypatch
) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _evidence(connection)
    factory = sessionmaker(engine, expire_on_commit=False)
    result_id = _record(factory, evidence_id, _concepts(multiple=True))
    monkeypatch.setattr(adapters, "concepts_fingerprint", lambda _: (FINGERPRINT_SCHEMA, "d" * 64))
    with pytest.raises(DerivedResultDeterminismViolation):
        _record(factory, evidence_id, _concepts(multiple=True))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concept")) == 2
        assert (
            connection.scalar(
                text("SELECT result_fingerprint FROM cfdi_concepts_result WHERE id = :id"),
                {"id": result_id},
            )
            != "d" * 64
        )
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parse_execution")) == 1


def test_repository_rejects_parser_schema_mismatch_before_new_execution(
    engine, monkeypatch
) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _evidence(connection)
    factory = sessionmaker(engine, expire_on_commit=False)
    _record(factory, evidence_id, _concepts())
    monkeypatch.setattr(adapters, "concepts_fingerprint", lambda _: (SCHEMA_V2, "d" * 64))
    with pytest.raises(ParserFingerprintSchemaMismatch):
        _record(factory, evidence_id, _concepts())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parser_schema")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parse_execution")) == 1


def test_child_write_failure_rolls_back_result_atomically(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _evidence(connection)
    original_model = adapters.CfdiConceptModel

    def invalid_child(**values):
        return original_model(**(values | {"concept_index": -1}))

    monkeypatch.setattr(adapters, "CfdiConceptModel", invalid_child)
    factory = sessionmaker(engine, expire_on_commit=False)
    uow = SqlAlchemyUnitOfWork(factory)
    with uow:
        repository = SqlAlchemyCfdiConceptsRepository(uow)
        with pytest.raises(IntegrityError):
            repository.record_success(evidence_id, _concepts(), CONFIG_A)
        repository.record_failure(evidence_id, CONFIG_B, ValueError("child rejected"))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 0
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concept")) == 0
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM cfdi_concepts_parse_execution WHERE status = 'SUCCEEDED'"
                )
            )
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM cfdi_concepts_parse_execution WHERE status = 'FAILED'")
            )
            == 1
        )


def test_serial_idempotency_reuses_one_complete_child_set(engine) -> None:
    with engine.begin() as connection:
        evidence_id = _evidence(connection)
    factory = sessionmaker(engine, expire_on_commit=False)
    parsed = _concepts(multiple=True)
    assert {_record(factory, evidence_id, parsed) for _ in range(3)}.__len__() == 1
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parser_schema")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concept")) == 2
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parse_execution")) == 3


def test_deterministic_concurrent_result_registration(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _evidence(connection)
        _insert_registry(connection)
    reached = Barrier(2)
    monkeypatch.setattr(adapters, "_after_missing_concepts_result", reached.wait)
    factory = sessionmaker(engine, expire_on_commit=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result_ids = list(
            pool.map(lambda _: _record(factory, evidence_id, _concepts(multiple=True)), range(2))
        )
    assert result_ids[0] == result_ids[1]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parser_schema")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concept")) == 2
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parse_execution")) == 2


def test_deterministic_concurrent_parser_schema_registration(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _evidence(connection)
    reached = Barrier(2)
    monkeypatch.setattr(adapters, "_after_missing_concepts_parser_schema", reached.wait)
    factory = sessionmaker(engine, expire_on_commit=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result_ids = list(pool.map(lambda _: _record(factory, evidence_id, _concepts()), range(2)))
    assert result_ids[0] == result_ids[1]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parser_schema")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concept")) == 1
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_parse_execution")) == 2


def test_concurrent_promotions_are_serialized(engine, monkeypatch) -> None:
    import aurum.infrastructure.sqlalchemy_adapters as adapters

    with engine.begin() as connection:
        evidence_id = _evidence(connection)
        identity_id = _identity(connection, evidence_id)
    factory = sessionmaker(engine, expire_on_commit=False)
    first = _record(factory, evidence_id, _concepts(), CONFIG_A)
    second = _record(factory, evidence_id, _concepts(), CONFIG_B)
    first_locked, release_first = Event(), Event()

    def hold_first_lock() -> None:
        first_locked.set()
        release_first.wait(timeout=5)

    monkeypatch.setattr(adapters, "_after_identity_locked", hold_first_lock)

    def promote(result_id: int) -> None:
        with SqlAlchemyUnitOfWork(factory) as uow:
            SqlAlchemyCfdiConceptsRepository(uow).promote(identity_id, result_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(promote, first)
        assert first_locked.wait(timeout=5)
        second_future = pool.submit(promote, second)
        release_first.set()
        first_future.result()
        second_future.result()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_current")) == 1
        assert connection.scalar(text("SELECT result_id FROM cfdi_concepts_current")) == second
        assert connection.scalar(text("SELECT count(*) FROM cfdi_concepts_result")) == 2
