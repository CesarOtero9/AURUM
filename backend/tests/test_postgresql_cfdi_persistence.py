"""Real PostgreSQL integration tests; destructive operations require a test database."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from alembic import command
from aurum.application.cfdi_ingestion import IngestCfdiXml
from aurum.domain.cfdi_identity import (
    CfdiUuid,
    EvidenceIdentityMismatch,
    IngestionOutcome,
    OriginalXml,
    XmlEvidence,
)
from aurum.infrastructure.sqlalchemy_adapters import (
    SqlAlchemyCfdiIdentityRepository,
    SqlAlchemyIngestionRecordRepository,
    SqlAlchemyXmlEvidenceStore,
)
from aurum.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from aurum.infrastructure.xml_cfdi_identity_reader import SecureCfdiIdentityReader

TEST_DATABASE_URL = os.environ.get("AURUM_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="AURUM_TEST_DATABASE_URL is not configured; real PostgreSQL is required",
)
UUID_A = "039D171E-773B-495C-881F-BBEFBC8991C2"
UUID_B = "123E4567-E89B-42D3-A456-426614174000"


def _url() -> URL:
    assert TEST_DATABASE_URL is not None
    url = make_url(TEST_DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("AURUM_TEST_DATABASE_URL must use PostgreSQL")
    if not url.database or "test" not in url.database.lower():
        raise RuntimeError("AURUM_TEST_DATABASE_URL database name must contain 'test'")
    return url


def _xml(value: str = UUID_A, extra: bytes = b"") -> bytes:
    return (
        b"<cfdi:Comprobante xmlns:cfdi='http://www.sat.gob.mx/cfd/4' "
        b"xmlns:tfd='http://www.sat.gob.mx/TimbreFiscalDigital'><cfdi:Complemento>"
        b"<tfd:TimbreFiscalDigital UUID='"
        + value.encode()
        + b"' /></cfdi:Complemento>"
        + extra
        + b"</cfdi:Comprobante>"
    )


@pytest.fixture(scope="module")
def database_url() -> str:
    return _url().render_as_string(hide_password=False)


@pytest.fixture(scope="module")
def migrated_database(database_url: str) -> str:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


@pytest.fixture
def engine(migrated_database: str):
    engine = create_engine(migrated_database)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE ingestion_record, identity_conflict, cfdi_identity, "
                "xml_evidence RESTART IDENTITY"
            )
        )
    yield engine
    engine.dispose()


def _insert_evidence(connection, content: bytes, fiscal_uuid: str = UUID_A) -> int:
    result = connection.execute(
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
    )
    return int(result.scalar_one())


def _insert_identity(connection, evidence_id: int, fiscal_uuid: str = UUID_A) -> int:
    return int(
        connection.execute(
            text(
                "INSERT INTO cfdi_identity (fiscal_uuid, authoritative_evidence_id) "
                "VALUES (:uuid, :evidence) RETURNING id"
            ),
            {"uuid": fiscal_uuid, "evidence": evidence_id},
        ).scalar_one()
    )


def _use_case(factory: sessionmaker, xml: bytes) -> IngestCfdiXml:
    uow = SqlAlchemyUnitOfWork(factory)
    evidence = SqlAlchemyXmlEvidenceStore(uow)
    identities = SqlAlchemyCfdiIdentityRepository(uow, evidence)
    return IngestCfdiXml(
        SecureCfdiIdentityReader(),
        evidence,
        identities,
        SqlAlchemyIngestionRecordRepository(uow, identities, evidence),
        uow,
    )


def _evidence(xml: bytes) -> XmlEvidence:
    return XmlEvidence.from_original_xml(OriginalXml(xml))


def test_alembic_upgrade_from_empty_database(migrated_database: str) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", migrated_database)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(migrated_database)
    try:
        assert {"xml_evidence", "cfdi_identity", "identity_conflict", "ingestion_record"} <= set(
            inspect(engine).get_table_names()
        )
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "20260908_01"
            )
    finally:
        engine.dispose()


def test_bytea_round_trip_is_exact(engine) -> None:
    content = _xml() + b"\x00\xff"
    with engine.begin() as connection:
        evidence_id = _insert_evidence(connection, content)
        assert (
            connection.execute(
                text("SELECT content FROM xml_evidence WHERE id=:id"), {"id": evidence_id}
            ).scalar_one()
            == content
        )


def test_sha256_unique(engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert_evidence(connection, _xml())
            _insert_evidence(connection, _xml())


def test_fiscal_uuid_unique(engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            first = _insert_evidence(connection, _xml())
            second = _insert_evidence(connection, _xml(extra=b" "))
            _insert_identity(connection, first)
            _insert_identity(connection, second)


def test_composite_identity_evidence_uuid_fk(engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            evidence = _insert_evidence(connection, _xml(), UUID_A)
            _insert_identity(connection, evidence, UUID_B)


def test_case_a_same_uuid_same_hash_reingested(engine) -> None:
    factory = sessionmaker(engine, expire_on_commit=False)
    first, second = (
        _use_case(factory, _xml()).ingest_cfdi_xml(_xml()),
        _use_case(factory, _xml()).ingest_cfdi_xml(_xml()),
    )
    assert (first.outcome, second.outcome) == (
        IngestionOutcome.ACCEPTED,
        IngestionOutcome.REINGESTED,
    )
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM xml_evidence")).scalar_one() == 1


def test_case_b_same_uuid_different_hash_conflict(engine) -> None:
    factory = sessionmaker(engine, expire_on_commit=False)
    _use_case(factory, _xml()).ingest_cfdi_xml(_xml())
    result = _use_case(factory, _xml(extra=b" ")).ingest_cfdi_xml(_xml(extra=b" "))
    assert result.outcome is IngestionOutcome.IDENTITY_CONFLICT
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM identity_conflict")).scalar_one() == 1


def test_case_c_same_hash_same_uuid_reingested(engine) -> None:
    test_case_a_same_uuid_same_hash_reingested(engine)


def test_case_d_same_hash_different_uuid_rejected(engine) -> None:
    factory = sessionmaker(engine, expire_on_commit=False)
    _use_case(factory, _xml()).ingest_cfdi_xml(_xml())
    # Same bytes cannot contain another extracted UUID; test the adapter-boundary invariant.
    with pytest.raises(EvidenceIdentityMismatch):
        with SqlAlchemyUnitOfWork(factory) as uow:
            SqlAlchemyXmlEvidenceStore(uow).store(_evidence(_xml()), CfdiUuid.from_raw(UUID_B))


def test_accepted_ingestion_record_is_consistent(engine) -> None:
    factory = sessionmaker(engine)
    _use_case(factory, _xml()).ingest_cfdi_xml(_xml())
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT evidence_id, authoritative_evidence_id, "
                "identity_conflict_id FROM ingestion_record"
            )
        ).one()
        assert row.evidence_id == row.authoritative_evidence_id and row.identity_conflict_id is None


def test_reingested_ingestion_record_is_consistent(engine) -> None:
    test_case_a_same_uuid_same_hash_reingested(engine)
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM ingestion_record WHERE outcome='REINGESTED' "
                    "AND evidence_id=authoritative_evidence_id AND identity_conflict_id IS NULL"
                )
            ).scalar_one()
            == 1
        )


def test_conflict_ingestion_record_is_consistent(engine) -> None:
    test_case_b_same_uuid_different_hash_conflict(engine)
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM ingestion_record WHERE outcome='IDENTITY_CONFLICT' "
                    "AND evidence_id<>authoritative_evidence_id "
                    "AND identity_conflict_id IS NOT NULL"
                )
            ).scalar_one()
            == 1
        )


def test_manual_incompatible_ingestion_state_is_rejected(engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            evidence = _insert_evidence(c, _xml())
            identity = _insert_identity(c, evidence)
            c.execute(
                text(
                    "INSERT INTO ingestion_record "
                    "(outcome,evidence_id,cfdi_identity_id,authoritative_evidence_id) "
                    "VALUES ('ACCEPTED',:e,:i,:bad)"
                ),
                {"e": evidence, "i": identity, "bad": evidence + 1},
            )


def test_delete_restrict(engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            evidence = _insert_evidence(c, _xml())
            _insert_identity(c, evidence)
            c.execute(text("DELETE FROM xml_evidence WHERE id=:id"), {"id": evidence})


def test_rollback_leaves_no_partial_state(engine) -> None:
    factory = sessionmaker(engine)
    with pytest.raises(RuntimeError):
        with SqlAlchemyUnitOfWork(factory) as uow:
            SqlAlchemyXmlEvidenceStore(uow).store(_evidence(_xml()), CfdiUuid.from_raw(UUID_A))
            raise RuntimeError("force rollback")
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM xml_evidence")).scalar_one() == 0


def _concurrent(factory: sessionmaker, xmls: list[bytes]) -> list[IngestionOutcome]:
    barrier, outcomes = Barrier(len(xmls)), []

    def run(xml: bytes) -> IngestionOutcome:
        barrier.wait(timeout=10)
        return _use_case(factory, xml).ingest_cfdi_xml(xml).outcome

    with ThreadPoolExecutor(max_workers=len(xmls)) as pool:
        for future in [pool.submit(run, xml) for xml in xmls]:
            outcomes.append(future.result(timeout=20))
    return outcomes


def test_concurrent_same_xml_is_accepted_then_reingested(engine) -> None:
    outcomes = _concurrent(sessionmaker(engine), [_xml(), _xml()])
    assert sorted(outcomes) == [IngestionOutcome.ACCEPTED, IngestionOutcome.REINGESTED]
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM ingestion_record")).scalar_one() == 2


def test_concurrent_same_uuid_different_xml_creates_conflict(engine) -> None:
    outcomes = _concurrent(sessionmaker(engine), [_xml(), _xml(extra=b" ")])
    assert sorted(outcomes) == [IngestionOutcome.ACCEPTED, IngestionOutcome.IDENTITY_CONFLICT]
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM identity_conflict")).scalar_one() == 1


def test_concurrent_same_conflict_creates_one_incident(engine) -> None:
    factory = sessionmaker(engine)
    _use_case(factory, _xml()).ingest_cfdi_xml(_xml())
    outcomes = _concurrent(factory, [_xml(extra=b" "), _xml(extra=b" ")])
    assert outcomes == [IngestionOutcome.IDENTITY_CONFLICT] * 2
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM identity_conflict")).scalar_one() == 1
        assert (
            c.execute(
                text("SELECT count(*) FROM ingestion_record WHERE outcome='IDENTITY_CONFLICT'")
            ).scalar_one()
            == 2
        )
