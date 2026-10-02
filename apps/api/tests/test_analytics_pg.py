"""Real PostgreSQL migration/persistence tests; CI provides a dedicated database.

Run SFR_TEST_ANALYTICS_DATABASE_URL=postgresql+psycopg://... uv run pytest
apps/api/tests/test_analytics_pg.py --no-cov. Never substitute SQLite here.
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from conftest import FakeBackend
from fastapi.testclient import TestClient
from sqlalchemy import insert, inspect, select, text

from sfr_api.analytics.migrate import migrate
from sfr_api.analytics.models import Context, ProductEvent, Search
from sfr_api.analytics.store import DurableStore, engine_for
from sfr_api.main import create_app
from sfr_api.service import MatchService
from sfr_api.settings import ApiSettings

pytestmark = pytest.mark.analytics_pg


@pytest.fixture
def database_url():
    url = os.environ.get("SFR_TEST_ANALYTICS_DATABASE_URL")
    if not url:
        if os.environ.get("SFR_REQUIRE_ANALYTICS_PG") == "1":
            pytest.fail("Real PostgreSQL is required for this CI job")
        pytest.skip("Dedicated PostgreSQL URL not configured")
    assert url.startswith("postgresql+psycopg://")
    migrate(url)
    return url


def synthetic_event(visit, search, name="visit_started", seq=0):
    return {
        "event_id": str(uuid4()),
        "visit_id": str(visit),
        "search_id": str(search),
        "name": name,
        "client_at": "2035-01-01T00:00:00+03:00",
        "client_seq": seq,
        "page": "home",
        "data": {},
    }


def test_migration_reentrant_and_real_postgres_types(database_url):
    migrate(database_url)
    engine = engine_for(database_url)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM analytics_alembic_version")
            ).scalar_one()
            == "analytics_0003"
        )
        assert connection.execute(text("SHOW timezone")).scalar_one() == "UTC"
        actual = dict(
            connection.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name='analytics_events'"
                )
            ).all()
        )
        assert actual["received_at"] == "timestamp with time zone"
        assert actual["client_at"] == "timestamp with time zone"
        assert actual["data"] == "jsonb"
    engine.dispose()


def test_real_persistence_outage_restart_and_idempotent_replay(database_url, tmp_path: Path):
    # During outage the acknowledged file survives a full store/app recreation.
    visit, search = uuid4(), uuid4()
    entry = synthetic_event(visit, search)
    settings = ApiSettings(
        warmup=False,
        analytics_database_url="postgresql+psycopg://synthetic:synthetic@127.0.0.1:1/synthetic",
        analytics_spool_dir=tmp_path / "spool",
        analytics_disk_reserve_bytes=0,
        analytics_replay_seconds=3600,
    )
    with TestClient(create_app(settings, MatchService(FakeBackend(), settings))) as client:
        assert client.post("/api/events", json={"events": [entry, entry]}).status_code == 200
        assert (
            client.post(
                "/api/match",
                json={"query": "  synthetic user@example.test  "},
                headers={
                    "X-SFR-Visit-ID": str(visit),
                    "X-SFR-Search-ID": str(search),
                    "X-Request-ID": str(uuid4()),
                },
            ).status_code
            == 200
        )
    restored = DurableStore(database_url, tmp_path / "spool", reserve_bytes=0)
    assert restored.replay()["persisted"] == 3
    assert restored.replay()["persisted"] == 0
    # Re-delivery of the identical immutable event in a new journal remains one row.
    entry |= {
        "received_at": datetime.now(UTC).isoformat(),
        "app_version": "synthetic",
        "traffic_type": "unclassified",
        "schema_version": 1,
        "request_id": None,
        "private_context": {
            "event_id": entry["event_id"],
            "raw_ip": None,
            "url": None,
            "referer": None,
            "diagnostic_headers": {},
        },
    }
    restored.append("events", [entry])
    assert restored.replay()["persisted"] == 1
    with restored.engine.connect() as connection:
        events = connection.execute(
            select(ProductEvent).where(ProductEvent.visit_id == visit)
        ).all()
        assert len(events) == 1
        facts = (
            connection.execute(select(Search.__table__).where(Search.search_id == search))
            .mappings()
            .one()
        )
        assert facts["status"] == 200 and facts["payload"]["cache_hit"] is False
        context = (
            connection.execute(select(Context.__table__).where(Context.search_id == search))
            .mappings()
            .one()
        )
        assert context["raw_query"] == "  synthetic user@example.test  "
        assert context["normalized_query"] == "synthetic user@example.test"
        assert facts["persisted_at"] >= facts["received_at"]
    restored.engine.dispose()


def test_late_client_events_do_not_replace_server_time(database_url, tmp_path: Path):
    store = DurableStore(database_url, tmp_path / "spool", reserve_bytes=0)
    visit, search = uuid4(), uuid4()
    records = []
    for seq, name in [(2, "profile_opened"), (1, "results_shown")]:
        record = synthetic_event(visit, search, name, seq)
        record |= {
            "received_at": datetime.now(UTC).isoformat(),
            "app_version": "synthetic",
            "traffic_type": "suspected_bot",
            "schema_version": 1,
            "request_id": None,
            "private_context": {
                "event_id": record["event_id"],
                "raw_ip": None,
                "url": None,
                "referer": None,
                "diagnostic_headers": {},
            },
        }
        records.append(record)
    store.append("events", records)
    assert store.replay()["errors"] == 0
    with store.engine.connect() as connection:
        events = (
            connection.execute(
                select(ProductEvent.__table__)
                .where(ProductEvent.visit_id == visit)
                .order_by(ProductEvent.client_seq)
            )
            .mappings()
            .all()
        )
        assert [e["client_seq"] for e in events] == [1, 2]
        assert all(e["client_at"] > e["received_at"] for e in events)
        assert all(e["traffic_type"] == "suspected_bot" for e in events)
    store.engine.dispose()


def test_runtime_role_minimal_permissions(database_url, tmp_path: Path):
    """A real PG role can write facts but cannot read private queries or mutate history."""
    import psycopg
    from psycopg import sql

    runtime, reader = f"sfr_runtime_{uuid4().hex[:12]}", f"sfr_reader_{uuid4().hex[:12]}"
    with psycopg.connect(database_url.replace("postgresql+psycopg://", "postgresql://")) as conn:
        for role in (runtime, reader):
            conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
    migrate(database_url, runtime_role=runtime, reader_role=reader)
    engine = engine_for(database_url)
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT has_table_privilege(:role,'analytics_context','INSERT')"),
            {"role": runtime},
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_table_privilege(:role,'analytics_context','SELECT')"),
            {"role": runtime},
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_table_privilege(:role,'analytics_searches','UPDATE')"),
            {"role": runtime},
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_table_privilege(:role,'analytics_searches','DELETE')"),
            {"role": runtime},
        ).scalar_one()
        assert conn.execute(
            text("SELECT has_column_privilege(:role,'analytics_searches','search_id','SELECT')"),
            {"role": runtime},
        ).scalar_one()
        assert conn.execute(
            text("SELECT has_table_privilege(:role,'analytics_context','SELECT')"), {"role": reader}
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_table_privilege(:role,'analytics_context','INSERT')"), {"role": reader}
        ).scalar_one()
    engine.dispose()
    # Exercise the real replay SQL under the restricted role, including RETURNING
    # and private-context foreign keys, rather than merely inspecting GRANTs.
    from sqlalchemy import event as sqlalchemy_event

    runtime_store = DurableStore(database_url, tmp_path / "runtime-spool", reserve_bytes=0)

    @sqlalchemy_event.listens_for(runtime_store.engine, "connect")
    def set_runtime_role(connection, record):
        connection.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(runtime)))
        connection.commit()

    record = synthetic_event(uuid4(), uuid4())
    record |= {
        "received_at": datetime.now(UTC).isoformat(),
        "app_version": "synthetic",
        "traffic_type": "unclassified",
        "schema_version": 1,
        "request_id": None,
        "private_context": {
            "event_id": record["event_id"],
            "raw_ip": None,
            "url": None,
            "referer": None,
            "diagnostic_headers": {},
        },
    }
    runtime_store.append("events", [record])
    assert runtime_store.replay()["persisted"] == 1
    assert runtime_store.diagnostics()["pending_count"] == 0
    runtime_store.engine.dispose()


def test_upgrade_existing_0001_preserves_seeded_search_and_private_context(database_url):
    # Keep the current public DB and all of its data intact. This schema contains
    # only this test's synthetic legacy database and is retained as evidence.
    import sfr_api.analytics.migrate as migration_module

    schema = "sfr_legacy_upgrade_" + uuid4().hex
    search_id, request_id, visit_id = uuid4(), uuid4(), uuid4()
    engine = engine_for(database_url)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config()
        config.set_main_option(
            "script_location", str(Path(migration_module.__file__).parent / "alembic")
        )
        config.attributes["connection"] = connection
        command.upgrade(config, "analytics_0001")
        assert (
            connection.execute(
                text("SELECT version_num FROM analytics_alembic_version")
            ).scalar_one()
            == "analytics_0001"
        )
        now = datetime.now(UTC)
        connection.execute(
            insert(Search.__table__).values(
                search_id=search_id,
                request_id=request_id,
                visit_id=visit_id,
                received_at=now,
                completed_at=now,
                status=200,
                outcome="success",
                payload={
                    "schema_version": 1,
                    "app_version": "legacy-test",
                    "model": "synthetic",
                    "index_version": "synthetic-v1",
                    "cache_hit": False,
                    "confidence": "ok",
                    "k": 1,
                    "results": [{"author_id": "A1", "rank": 1, "score": 0.5, "grade": "high"}],
                },
            )
        )
        connection.execute(
            insert(Context.__table__).values(
                search_id=search_id,
                raw_query="  synthetic legacy contact user@example.test  ",
                normalized_query="synthetic legacy contact user@example.test",
                raw_ip="192.0.2.1",
                url="https://example.test/results",
                referer=None,
                diagnostic_headers={"user-agent": "SFR-Technical migration-test"},
            )
        )
        before_search = dict(connection.execute(select(Search.__table__)).mappings().one())
        before_context = dict(connection.execute(select(Context.__table__)).mappings().one())
        assert "ingest_request_id" not in {
            column["name"]
            for column in inspect(connection).get_columns("analytics_event_context", schema=schema)
        }
        command.upgrade(config, "head")
        assert (
            connection.execute(
                text("SELECT version_num FROM analytics_alembic_version")
            ).scalar_one()
            == "analytics_0003"
        )
        after_search = dict(connection.execute(select(Search.__table__)).mappings().one())
        after_context = dict(connection.execute(select(Context.__table__)).mappings().one())
        assert after_search == before_search
        assert after_context == before_context
        inspector = inspect(connection)
        assert "uq_analytics_visit_seq" in {
            item["name"]
            for item in inspector.get_unique_constraints("analytics_events", schema=schema)
        }
        assert "ingest_request_id" in {
            column["name"]
            for column in inspector.get_columns("analytics_event_context", schema=schema)
        }
        # Upgrade is also safe when invoked again with retained legacy records.
        command.upgrade(config, "head")
        assert dict(connection.execute(select(Search.__table__)).mappings().one()) == before_search
        assert (
            dict(connection.execute(select(Context.__table__)).mappings().one()) == before_context
        )
    engine.dispose()


@pytest.mark.parametrize("bad_kind", ["event_jsonb", "context_jsonb", "search_text"])
def test_permanent_nul_record_is_preserved_and_does_not_block_valid_replay(
    database_url, tmp_path: Path, bad_kind
):
    from sqlalchemy import event as sqlalchemy_event

    import sfr_api.analytics.migrate as migration_module

    schema = "sfr_nul_replay_" + uuid4().hex
    journal = DurableStore(database_url, tmp_path / "isolated-spool", reserve_bytes=0)
    with journal.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config()
        config.set_main_option(
            "script_location", str(Path(migration_module.__file__).parent / "alembic")
        )
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    journal.engine.dispose()

    @sqlalchemy_event.listens_for(journal.engine, "connect")
    def select_isolated_schema(connection, record):
        from psycopg import sql

        connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        connection.commit()

    valid = synthetic_event(uuid4(), uuid4())
    valid |= {
        "received_at": datetime.now(UTC).isoformat(),
        "app_version": "synthetic",
        "traffic_type": "unclassified",
        "schema_version": 1,
        "request_id": None,
        "private_context": {
            "event_id": valid["event_id"],
            "raw_ip": None,
            "url": None,
            "referer": None,
            "diagnostic_headers": {},
        },
    }
    if bad_kind in {"event_jsonb", "context_jsonb"}:
        bad = {
            **valid,
            "event_id": str(uuid4()),
            "visit_id": str(uuid4()),
            "data": {"author_id": "synthetic\x00unsupported"},
        }
        bad["private_context"] = {**valid["private_context"], "event_id": bad["event_id"]}
        if bad_kind == "context_jsonb":
            bad["data"] = {}
            bad["private_context"]["diagnostic_headers"] = {
                "user-agent": "synthetic\x00unsupported"
            }
        kind = "events"
    else:
        sid = str(uuid4())
        now = datetime.now(UTC).isoformat()
        bad = {
            "search": {
                "search_id": sid,
                "request_id": str(uuid4()),
                "visit_id": None,
                "received_at": now,
                "completed_at": now,
                "status": 200,
                "outcome": "success",
                "payload": {"schema_version": 1},
            },
            "context": {
                "search_id": sid,
                "raw_query": "synthetic\x00unsupported",
                "normalized_query": "synthetic\x00unsupported",
                "raw_ip": None,
                "url": None,
                "referer": None,
                "diagnostic_headers": {},
            },
        }
        kind = "search"
    # Probe only safe exception classification, without SQL/parameters/message.
    try:
        journal._persist({"version": 1, "kind": kind, "records": [bad]})
    except Exception as error:
        original = getattr(error, "orig", None)
        print(
            {
                "kind": bad_kind,
                "exception_class": type(error).__name__,
                "driver_class": type(original).__name__,
                "sqlstate": getattr(original, "sqlstate", None),
            }
        )
    else:
        pytest.fail("PostgreSQL unexpectedly accepted unsupported NUL")
    journal.append(kind, [bad])
    bad_path = next((journal.root / "pending").glob("*.json"))
    bad_bytes = bad_path.read_bytes()
    journal.append("events", [valid])
    result = journal.replay()
    assert result == {"persisted": 1, "quarantined": 1, "errors": 0}
    assert (journal.root / "quarantine" / bad_path.name).read_bytes() == bad_bytes
    assert journal.diagnostics()["incomplete"]
    assert journal.diagnostics()["pending_count"] == 0
    with journal.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM analytics_events")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM analytics_searches")).scalar_one() == 0
    assert journal.replay() == {"persisted": 0, "quarantined": 0, "errors": 0}
    journal.engine.dispose()
