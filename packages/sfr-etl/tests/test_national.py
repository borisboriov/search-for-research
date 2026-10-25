import json
from pathlib import Path

import httpx
import pytest

from sfr_core.settings import Settings
from sfr_etl.national import FILTERS, NationalRegistry, atomic_json


def settings() -> Settings:
    return Settings(openalex_mailto="test@example.com", openalex_api_key="SECRET", _env_file=None)


def author(number: int, *, eligible: bool = True) -> dict:
    return {
        "id": f"https://openalex.org/A{number}",
        "works_count": 20 if eligible else 1,
        "summary_stats": {"h_index": 7},
        "counts_by_year": [{"year": 2026, "works_count": 1}],
        "last_known_institutions": [{"id": "https://openalex.org/I1", "country_code": "RU"}],
        "extra": {"preserve": True},
    }


def page(records: list, cursor: str | None, count: int = 3) -> dict:
    return {"meta": {"count": count, "next_cursor": cursor}, "results": records}


def make(root: Path, handler) -> NationalRegistry:
    return NationalRegistry(
        root,
        settings(),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        min_free_bytes=0,
    )


def budget(remaining: float = 1) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "api_key": "SECRET",
            "rate_limit": {
                "daily_remaining_usd": remaining,
                "endpoint_costs_usd": {"list": 0.0001, "singleton": 0},
                "resets_at": "2026-10-08T00:00:00Z",
            },
        },
    )


def test_resume_duplicates_complete_and_idempotent(tmp_path: Path) -> None:
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.url.params["mailto"] == "test@example.com"
        if request.url.path == "/rate-limit":
            return budget()
        assert request.url.params["per_page"] == "100"
        assert request.url.params["filter"] == FILTERS[request.url.path[1:]]
        if request.url.path == "/institutions":
            return httpx.Response(
                200, json=page([{"id": "https://openalex.org/I1", "country_code": "RU"}], None)
            )
        return httpx.Response(200, json=page([author(1), author(2, eligible=False)], "second"))

    r = make(tmp_path, handler)
    envelope = {
        "kind": "authors",
        "cursor": "*",
        "fetched_at": "now",
        "body": page([author(1), author(2, eligible=False)], "second"),
    }
    atomic_json(r.cache_path("authors", "*"), envelope)
    r.close()  # Crash after cache fsync, before cursor transaction.

    def resumed(request):
        if request.url.path == "/authors":
            calls.append("resumed")
            assert request.url.params["cursor"] == "second"
            return httpx.Response(200, json=page([author(1), author(3)], None, 4))
        return handler(request)

    r = make(tmp_path, resumed)
    result = r.run()
    assert result["status"] == "complete"
    assert result["authors"]["unique"] == 3
    assert result["authors"]["duplicates"] == 1
    assert result["authors"]["api_count_min"] == 3
    assert result["authors"]["api_count_max"] == 4
    assert result["candidates"] == 2
    assert json.loads(
        r.db.execute("SELECT raw FROM records WHERE id='https://openalex.org/A2'").fetchone()[0]
    )["extra"]["preserve"]
    before = len(calls)
    assert r.run()["authors"] == result["authors"]
    assert len(calls) == before
    assert "SECRET" not in (tmp_path / "status.json").read_text()
    r.close()


def test_quota_prepaid_not_used_and_resume(tmp_path: Path) -> None:
    calls = []

    def exhausted(request):
        calls.append(request.url.path)
        return budget(0)

    r = make(tmp_path, exhausted)
    assert r.run()["status"] == "waiting_quota"
    assert calls == ["/rate-limit"]
    assert r.db.execute("SELECT cursor FROM state WHERE kind='authors'").fetchone()[0] == "*"
    r.close()

    def restored(request):
        if request.url.path == "/rate-limit":
            return budget()
        return httpx.Response(200, json=page([], None, 0))

    r = make(tmp_path, restored)
    assert r.run()["status"] == "complete"
    r.close()


def test_failed_page_does_not_advance_and_429_not_retried(tmp_path: Path) -> None:
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/rate-limit":
            return budget(1 if len(calls) == 1 else 0)
        return httpx.Response(429)

    r = make(tmp_path, handler)
    assert r.run()["status"] == "waiting_quota"
    assert calls == ["/rate-limit", "/institutions", "/rate-limit"]
    assert r.verify()["authors"]["pages"] == 0
    r.close()


def test_corrupt_cache_and_cursor_cycle_fail_closed(tmp_path: Path) -> None:
    r = make(tmp_path, lambda _: budget())
    env = {"kind": "authors", "cursor": "*", "fetched_at": "now", "body": page([author(1)], "*")}
    atomic_json(r.cache_path("authors", "*"), env)
    with pytest.raises(ValueError, match="cycle"):
        r.consume("authors", "*", env)
    env["body"] = page([author(1)], None)
    atomic_json(r.cache_path("authors", "*"), env)
    r.consume("authors", "*", env)
    r.cache_path("authors", "*").write_text("corrupted")
    with pytest.raises(ValueError, match="checksum"):
        r.verify()
    r.close()


def test_disk_lock_and_settings_guard(tmp_path: Path) -> None:
    r = make(tmp_path, lambda _: budget())
    with pytest.raises(RuntimeError, match="owns"):
        make(tmp_path, lambda _: budget())
    r.min_free_bytes = 10**30
    with pytest.raises(OSError, match="reserve"):
        r.run()
    r.close()
    changed = settings()
    changed.supervisor_min_works += 1
    with pytest.raises(ValueError, match="configuration"):
        NationalRegistry(tmp_path, changed)


def test_backoff_transport_and_server_failures(tmp_path: Path, monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr("sfr_etl.national.time.sleep", lambda delay: sleeps.append(delay))
    attempts = 0

    def handler(request):
        nonlocal attempts
        if request.url.path == "/rate-limit":
            return budget()
        attempts += 1
        if attempts == 1:
            raise httpx.ReadError("SECRET must never escape")
        if attempts == 2:
            return httpx.Response(503, headers={"Retry-After": "3"})
        return httpx.Response(200, json=page([], None))

    r = make(tmp_path, handler)
    r.limiter = type("NoWait", (), {"acquire": lambda self: None})()
    assert r.request("/authors", {})["results"] == []
    assert sleeps == [1, 3]
    assert (
        r.db.execute("SELECT COUNT(*) FROM requests WHERE endpoint='/authors'").fetchone()[0] == 3
    )
    assert r.db.execute("SELECT COUNT(*) FROM requests WHERE status IS NULL").fetchone()[0] == 1
    r.close()


def test_schema_and_invalid_records_never_advance(tmp_path: Path) -> None:
    r = make(tmp_path, lambda _: httpx.Response(200, json={"rate_limit": {}}))
    with pytest.raises(RuntimeError, match="budget schema"):
        r.run()
    assert r.verify()["authors"]["pages"] == 0
    bad = author(2)
    bad["last_known_institutions"] = [{"country_code": None}]
    env = {
        "kind": "authors",
        "cursor": "*",
        "fetched_at": "now",
        "body": page([author(1), bad], None),
    }
    atomic_json(r.cache_path("authors", "*"), env)
    with pytest.raises(ValueError, match="outside"):
        r.consume("authors", "*", env)
    assert r.db.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
    r.close()


def test_readonly_inspection_during_run_and_registry_tamper(tmp_path: Path) -> None:
    r = make(tmp_path, lambda _: budget())
    env = {"kind": "authors", "cursor": "*", "fetched_at": "now", "body": page([author(1)], None)}
    atomic_json(r.cache_path("authors", "*"), env)
    r.consume("authors", "*", env)
    assert NationalRegistry.inspect(tmp_path)["authors"]["unique"] == 1
    assert not (tmp_path / "status.json").exists()
    with r.db:
        r.db.execute("DELETE FROM records")
    with pytest.raises(ValueError, match="Registered IDs"):
        NationalRegistry.inspect(tmp_path)
    r.close()


def test_retry_rechecks_free_budget_after_ambiguous_spend(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("sfr_etl.national.time.sleep", lambda _: None)
    probes = 0
    data_calls = 0

    def handler(request):
        nonlocal probes, data_calls
        if request.url.path == "/rate-limit":
            probes += 1
            return budget(0.0001 if probes == 1 else 0)
        data_calls += 1
        raise httpx.ReadError("Response lost after server charged last free credit")

    r = make(tmp_path, handler)
    assert r.run()["status"] == "waiting_quota"
    assert probes == 2
    assert data_calls == 1  # No retry into prepaid after exhausting free credit.
    assert r.verify()["institutions"]["pages"] == 0
    r.close()


def test_transient_429_backs_off_with_free_budget(tmp_path: Path, monkeypatch) -> None:
    delays = []
    monkeypatch.setattr("sfr_etl.national.time.sleep", lambda d: delays.append(d))
    calls = 0

    def handler(request):
        nonlocal calls
        if request.url.path == "/rate-limit":
            return budget()
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "4"})
        return httpx.Response(200, json=page([], None))

    r = make(tmp_path, handler)
    r.limiter = type("NoWait", (), {"acquire": lambda self: None})()
    assert r.request("/authors", {})["results"] == []
    assert delays == [4]
    r.close()


def test_cli_constructor_error_does_not_show_credentials(tmp_path: Path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from sfr_etl.cli import app

    r = make(tmp_path, lambda _: budget())
    monkeypatch.setattr("sfr_etl.cli.Settings", lambda **kwargs: settings())
    result = CliRunner().invoke(app, ["etl", "national", "--out", str(tmp_path)])
    assert result.exit_code == 1
    assert "RuntimeError" in result.output
    assert "SECRET" not in result.output
    assert "Traceback" not in result.output
    r.close()


def test_affiliated_org_redirects_failures_and_cache(tmp_path: Path) -> None:
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/rate-limit":
            return budget(0)  # Singleton is free even after list quota exhaustion.
        if request.url.path == "/institutions/I1":
            return httpx.Response(
                301, headers={"Location": "https://api.openalex.org/institutions/I2"}
            )
        if request.url.path == "/institutions/I2":
            return httpx.Response(
                200, json={"id": "https://openalex.org/I2", "country_code": "RU", "extra": 1}
            )
        return httpx.Response(404)

    r = make(tmp_path, handler)
    env = {"kind": "authors", "cursor": "*", "fetched_at": "now", "body": page([author(1)], None)}
    atomic_json(r.cache_path("authors", "*"), env)
    r.consume("authors", "*", env)
    r.resolve_affiliated_institutions()
    saved = json.loads((tmp_path / "affiliated_institutions/I1.json").read_text())
    assert [item["status"] for item in saved["chain"]] == [301, 200]
    assert saved["chain"][-1]["body"]["extra"] == 1
    before = len(calls)
    r.resolve_affiliated_institutions()
    assert len(calls) == before
    with r.db:
        value = author(2)
        value["last_known_institutions"][0]["id"] = "https://openalex.org/I3"
        r.db.execute(
            "INSERT INTO records VALUES ('authors',?,?,0)", (value["id"], json.dumps(value))
        )
    r.resolve_affiliated_institutions()
    assert (
        json.loads((tmp_path / "affiliated_institutions/I3.json").read_text())["chain"][-1][
            "status"
        ]
        == 404
    )
    r.close()
