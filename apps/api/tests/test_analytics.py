"""Durable delivery/security contract using synthetic data; PG tests are separate."""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from conftest import FakeBackend
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sfr_api.analytics.capture import safe_url
from sfr_api.analytics.contracts import EventBatch
from sfr_api.analytics.store import DurableStore, StorageUnavailable
from sfr_api.main import create_app
from sfr_api.service import MatchService
from sfr_api.settings import ApiSettings

DEAD_URL = "postgresql+psycopg://synthetic:synthetic@127.0.0.1:1/synthetic"


def event(**changes):
    return {
        "event_id": str(uuid4()),
        "visit_id": str(uuid4()),
        "name": "visit_started",
        "client_at": datetime.now(UTC).isoformat(),
        "client_seq": 0,
        "page": "home",
        **changes,
    }


def store(tmp_path: Path, **kwargs) -> DurableStore:
    return DurableStore(DEAD_URL, tmp_path / "spool", reserve_bytes=0, **kwargs)


def api(tmp_path: Path, **changes):
    settings = ApiSettings(
        warmup=False,
        analytics_database_url=DEAD_URL,
        analytics_spool_dir=tmp_path / "spool",
        analytics_disk_reserve_bytes=0,
        analytics_replay_seconds=3600,
        **changes,
    )
    return create_app(settings, MatchService(FakeBackend(), settings))


def test_event_ack_is_durable_before_database_available(tmp_path: Path):
    app = api(tmp_path)
    entry = event()
    with TestClient(app) as client:
        response = client.post("/api/events", json={"events": [entry]})
        assert response.status_code == 200
        assert response.json() == {"accepted": [entry["event_id"]]}
        paths = list((tmp_path / "spool" / "pending").glob("*.json"))
        assert len(paths) == 1
        saved = json.loads(paths[0].read_text())["records"][0]
        assert saved["event_id"] == entry["event_id"]
        assert saved["received_at"] != entry["client_at"]
        assert paths[0].stat().st_mode & 0o777 == 0o600
    restarted = store(tmp_path)
    assert restarted.diagnostics()["pending_count"] == 1
    assert restarted.replay()["errors"] == 1
    assert restarted.diagnostics()["pending_count"] == 1


def test_no_false_ack_on_capacity_or_disabled_receiver(tmp_path: Path):
    with TestClient(api(tmp_path, analytics_spool_max_bytes=1)) as client:
        assert client.post("/api/events", json={"events": [event()]}).status_code == 503
        assert client.post("/api/match", json={"query": "синтетическая физика"}).status_code == 200
    settings = ApiSettings(warmup=False)
    with TestClient(create_app(settings, MatchService(FakeBackend(), settings))) as client:
        assert client.post("/api/events", json={"events": [event()]}).status_code == 503


def test_event_body_and_schema_limits(tmp_path: Path):
    with TestClient(api(tmp_path)) as client:
        assert client.post("/api/events", content=b"x" * 16385).status_code == 413
        assert client.post("/api/events", json={"events": [event()] * 11}).status_code == 422
        assert (
            client.post(
                "/api/events", json={"events": [event(data={"query": "secret"})]}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/events", json={"events": [event(client_at="2026-10-01T00:00:00")]}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/events", json={"events": [event(data={"included": False})]}
            ).status_code
            == 200
        )


def test_original_query_and_server_facts_separate_from_private_context(tmp_path: Path):
    query = "  Синтетическое имя user@example.test  "
    app = api(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/match",
            json={"query": query},
            headers={
                "X-Request-ID": str(uuid4()),
                "X-SFR-Search-ID": str(uuid4()),
                "Authorization": "SECRET_AUTH",
                "Cookie": "SECRET_COOKIE",
                "X-Revalidate-Secret": "SECRET_REVALIDATE",
                "X-SFR-Page-URL": "https://user:SECRET_PASS@example.test/results?token=SECRET_URL#SECRET_HASH",
                "X-SFR-Referer": "https://example.test/?api_key=SECRET_KEY",
                "X-SFR-Client-IP": "192.0.2.200",
                "X-Forwarded-For": "192.0.2.201",
            },
        )
        assert response.status_code == 200
        assert response.headers["X-Request-ID"]
        records = [
            json.loads(path.read_text())["records"][0]
            for path in (tmp_path / "spool" / "pending").glob("*.json")
        ]
        record = records[0]
        assert record["context"]["raw_query"] == query
        assert record["context"]["normalized_query"] == query.strip()
        assert record["context"]["url"] == "https://example.test/results"
        assert record["context"]["raw_ip"] is None  # TestClient peer is not an IP/trusted proxy.
        assert query not in json.dumps(record["search"])
        assert record["search"]["payload"]["results"][0]["rank"] == 1
        assert "SECRET_" not in json.dumps(record)


def test_search_errors_not_confidence_none(tmp_path: Path):
    with TestClient(api(tmp_path)) as client:
        assert client.post("/api/match", json={"query": "x"}).status_code == 422
        assert client.post("/api/match", json={"query": "a" * 501}).status_code == 422
    for path in (tmp_path / "spool" / "pending").glob("*.json"):
        search = json.loads(path.read_text())["records"][0]["search"]
        assert search["status"] == 422
        assert search["outcome"] == "error"
        assert "confidence" not in search["payload"]


def test_quarantine_preserves_corrupt_record(tmp_path: Path):
    journal = store(tmp_path)
    path = tmp_path / "spool" / "pending" / "corrupt.json"
    path.write_text("{corrupt synthetic data")
    assert journal.replay()["quarantined"] == 1
    assert (
        tmp_path / "spool" / "quarantine" / "corrupt.json"
    ).read_text() == "{corrupt synthetic data"
    assert journal.diagnostics()["incomplete"]


def test_success_archives_without_losing_history(tmp_path: Path, monkeypatch):
    journal = store(tmp_path)
    item = event()
    item.update(
        received_at=datetime.now(UTC).isoformat(),
        app_version="synthetic",
        traffic_type="unclassified",
        private_context={
            "event_id": item["event_id"],
            "raw_ip": None,
            "url": None,
            "referer": None,
            "diagnostic_headers": {},
        },
    )
    journal.append("events", [item])
    monkeypatch.setattr(journal, "_persist", lambda envelope: None)
    assert journal.replay()["persisted"] == 1
    assert journal.diagnostics()["pending_count"] == 0
    archived = next((tmp_path / "spool" / "archive").glob("*.gz"))
    assert (
        json.loads(gzip.decompress(archived.read_bytes()))["records"][0]["event_id"]
        == item["event_id"]
    )
    assert journal.replay()["persisted"] == 0


def test_disk_full_keeps_search_available_and_events_unacknowledged(tmp_path: Path, monkeypatch):
    journal = store(tmp_path)
    monkeypatch.setattr(
        "sfr_api.analytics.store._atomic", lambda *args: (_ for _ in ()).throw(OSError("synthetic"))
    )
    with pytest.raises(StorageUnavailable):
        journal.append("events", [event()])


def test_contract_does_not_accept_unknown_secrets():
    with pytest.raises(ValidationError):
        EventBatch.model_validate({"events": [event(Authorization="synthetic")]})
    assert safe_url("https://user:pw@example.test/a?token=x#secret") == "https://example.test/a"
    assert safe_url("javascript:alert(1)") is None


@pytest.mark.parametrize(
    "content",
    ["null", "[]", "{}", '{"version":1,"kind":"search","records":[{"search":{},"context":{}}]}'],
)
def test_invalid_shapes_do_not_block_replay(tmp_path: Path, content: str):
    journal = store(tmp_path)
    (tmp_path / "spool" / "pending" / "invalid.json").write_text(content)
    assert journal.replay()["quarantined"] == 1
    assert journal.diagnostics()["pending_count"] == 0


def test_stalled_disk_does_not_hold_search_or_falsely_ack_events(tmp_path: Path, monkeypatch):
    import time

    app = api(tmp_path)
    with TestClient(app) as client:
        original = app.state.analytics.append

        def slow_append(kind, records):
            time.sleep(0.8)
            original(kind, records)

        monkeypatch.setattr(app.state.analytics, "append", slow_append)
        started = time.monotonic()
        assert client.post("/api/match", json={"query": "synthetic physics"}).status_code == 200
        assert time.monotonic() - started < 0.6
        started = time.monotonic()
        assert client.post("/api/events", json={"events": [event()]}).status_code == 503
        assert time.monotonic() - started < 0.75


def test_analytics_invalid_configuration_does_not_disable_search(tmp_path: Path):
    settings = ApiSettings(
        warmup=False, analytics_database_url="invalid://", analytics_spool_dir=tmp_path / "spool"
    )
    with TestClient(create_app(settings, MatchService(FakeBackend(), settings))) as client:
        assert client.post("/api/match", json={"query": "synthetic physics"}).status_code == 200
        assert client.post("/api/events", json={"events": [event()]}).status_code == 503
