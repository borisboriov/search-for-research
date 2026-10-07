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
                "endpoint_costs_usd": {"list": 0.0001},
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
            return budget()
        return httpx.Response(429)

    r = make(tmp_path, handler)
    assert r.run()["status"] == "waiting_quota"
    assert calls == ["/rate-limit", "/authors"]
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
