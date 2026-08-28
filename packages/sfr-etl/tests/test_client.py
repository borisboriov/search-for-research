import json
from pathlib import Path

import httpx
import pytest
import respx

from sfr_etl.client import OpenAlexClient, RetryableStatusError

BASE = "https://api.openalex.org"


def make_client(tmp_path: Path, **kwargs: object) -> OpenAlexClient:
    defaults: dict[str, object] = {
        "base_url": BASE,
        "max_rps": 10_000.0,  # no throttling in tests
        "cache_dir": tmp_path / "raw",
        "max_attempts": 3,
        "backoff_max": 0.01,
    }
    defaults.update(kwargs)
    return OpenAlexClient("test@example.com", **defaults)  # type: ignore[arg-type]


def page(results: list[dict[str, object]], next_cursor: str | None) -> dict[str, object]:
    return {"meta": {"count": len(results), "next_cursor": next_cursor}, "results": results}


def test_requires_mailto(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mailto"):
        OpenAlexClient("", cache_dir=tmp_path)
    with pytest.raises(ValueError, match="mailto"):
        OpenAlexClient("not-an-email", cache_dir=tmp_path)


@respx.mock
def test_mailto_always_sent(tmp_path: Path) -> None:
    route = respx.get(f"{BASE}/works").mock(return_value=httpx.Response(200, json={"ok": True}))
    make_client(tmp_path).get("/works", {"filter": "x"})
    assert route.calls.last.request.url.params["mailto"] == "test@example.com"


@respx.mock
def test_cursor_pagination_two_pages(tmp_path: Path) -> None:
    respx.get(f"{BASE}/authors").mock(
        side_effect=[
            httpx.Response(200, json=page([{"id": "A1"}, {"id": "A2"}], "cur2")),
            httpx.Response(200, json=page([{"id": "A3"}], None)),
        ]
    )
    client = make_client(tmp_path)
    records = list(client.paginate("/authors", {"filter": "f"}, per_page=2))
    assert [r["id"] for r in records] == ["A1", "A2", "A3"]
    assert client.n_network_requests == 2


@respx.mock
def test_pagination_respects_max_records(tmp_path: Path) -> None:
    respx.get(f"{BASE}/authors").mock(
        side_effect=[
            httpx.Response(200, json=page([{"id": "A1"}, {"id": "A2"}], "cur2")),
            httpx.Response(200, json=page([{"id": "A3"}], None)),
        ]
    )
    client = make_client(tmp_path)
    records = list(client.paginate("/authors", per_page=2, max_records=2))
    assert len(records) == 2
    assert client.n_network_requests == 1  # second page never requested


@respx.mock
def test_retry_on_429_then_success(tmp_path: Path) -> None:
    respx.get(f"{BASE}/works").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    client = make_client(tmp_path)
    assert client.get("/works") == {"ok": True}
    assert client.n_network_requests == 2


@respx.mock
def test_retry_exhausted_raises(tmp_path: Path) -> None:
    respx.get(f"{BASE}/works").mock(return_value=httpx.Response(503))
    client = make_client(tmp_path)
    with pytest.raises(RetryableStatusError):
        client.get("/works")
    assert client.n_network_requests == 3  # max_attempts


@respx.mock
def test_4xx_not_retried(tmp_path: Path) -> None:
    respx.get(f"{BASE}/works").mock(return_value=httpx.Response(404))
    client = make_client(tmp_path)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("/works")
    assert client.n_network_requests == 1


@respx.mock
def test_cache_hit_skips_network(tmp_path: Path) -> None:
    route = respx.get(f"{BASE}/works").mock(return_value=httpx.Response(200, json={"n": 1}))
    client = make_client(tmp_path)
    assert client.get("/works", {"filter": "x"}) == {"n": 1}
    assert client.get("/works", {"filter": "x"}) == {"n": 1}
    assert route.call_count == 1
    assert client.n_cache_hits == 1
    # different params → different cache key → network again
    client.get("/works", {"filter": "y"})
    assert route.call_count == 2


@respx.mock
def test_refresh_bypasses_cache_read(tmp_path: Path) -> None:
    route = respx.get(f"{BASE}/works").mock(return_value=httpx.Response(200, json={"n": 1}))
    make_client(tmp_path).get("/works")
    refreshing = make_client(tmp_path, refresh=True)
    refreshing.get("/works")
    assert route.call_count == 2


@respx.mock
def test_cache_key_ignores_mailto(tmp_path: Path) -> None:
    route = respx.get(f"{BASE}/works").mock(return_value=httpx.Response(200, json={"n": 1}))
    make_client(tmp_path).get("/works")
    other = OpenAlexClient(
        "other@example.com", base_url=BASE, max_rps=10_000.0, cache_dir=tmp_path / "raw"
    )
    other.get("/works")
    assert route.call_count == 1
    assert other.n_cache_hits == 1


@respx.mock
def test_corrupted_cache_refetches(tmp_path: Path) -> None:
    route = respx.get(f"{BASE}/works").mock(return_value=httpx.Response(200, json={"n": 1}))
    client = make_client(tmp_path)
    client.get("/works")
    for f in (tmp_path / "raw").glob("*.json"):
        f.write_text("{broken", encoding="utf-8")
    assert client.get("/works") == {"n": 1}
    assert route.call_count == 2


@respx.mock
def test_cache_file_is_valid_envelope(tmp_path: Path) -> None:
    respx.get(f"{BASE}/works").mock(return_value=httpx.Response(200, json={"n": 1}))
    client = make_client(tmp_path)
    client.get("/works", {"filter": "x"})
    files = list((tmp_path / "raw").glob("*.json"))
    assert len(files) == 1
    envelope = json.loads(files[0].read_text(encoding="utf-8"))
    assert envelope["path"] == "/works"
    assert envelope["params"] == {"filter": "x"}
    assert "mailto" not in envelope["params"]
    assert envelope["body"] == {"n": 1}
