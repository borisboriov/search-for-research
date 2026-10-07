"""Resumable national registry. No production DB, works or indexing operations."""

import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from sfr_core.settings import Settings
from sfr_etl.catalog import passes_heuristic
from sfr_etl.client import RateLimiter

FILTERS = {"institutions": "country_code:ru", "authors": "last_known_institutions.country_code:ru"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def atomic_json(path: Path, body: Any) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(body, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class WaitingQuota(Exception):
    """Free daily budget unavailable; do not fall through to prepaid balance."""


class NationalRegistry:
    """One process owns the directory; cache is durable before advancing its cursor."""

    def __init__(
        self,
        root: Path,
        settings: Settings,
        *,
        http: httpx.Client | None = None,
        min_free_bytes: int = 1024**3,
    ) -> None:
        if not settings.openalex_api_key:
            raise ValueError("Existing OpenAlex API key required")
        self.root = root
        self.settings = settings
        self.min_free_bytes = min_free_bytes
        root.mkdir(parents=True, exist_ok=True)
        self.lock = (root / "collector.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError("Collector already owns this directory") from None
        self.http = http or httpx.Client(timeout=60)
        self.limiter = RateLimiter(min(10, max(0.1, settings.openalex_max_rps)))
        self.db = sqlite3.connect(root / "registry.sqlite3")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS state(kind TEXT PRIMARY KEY, cursor TEXT, done INTEGER);
            CREATE TABLE IF NOT EXISTS pages(kind TEXT, cursor TEXT, next_cursor TEXT,
                sha256 TEXT, records INTEGER, api_count INTEGER, fetched_at TEXT,
                PRIMARY KEY(kind,cursor));
            CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, raw TEXT, candidate INTEGER,
                PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, at TEXT, endpoint TEXT,
                status INTEGER, cost_usd TEXT);
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT);
        """)
        config: dict[str, Any] = {
            "filters": FILTERS,
            "per_page": 100,
            "year": datetime.now(UTC).year,
            "min_works": settings.supervisor_min_works,
            "min_h_index": settings.supervisor_min_h_index,
            "recent_years": settings.supervisor_recent_years,
        }
        previous = self.db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
        if previous:
            config["year"] = json.loads(previous[0])["year"]
        if previous and json.loads(previous[0]) != config:
            self.close()
            raise ValueError("Registry configuration changed; use its original settings/year")
        self.year = config["year"]
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('config',?)", (json.dumps(config),)
            )
            self.db.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('started_at',?)", (json.dumps(now()),)
            )
            for kind in FILTERS:
                self.db.execute("INSERT OR IGNORE INTO state VALUES (?, '*', 0)", (kind,))
        (root / "pages").mkdir(exist_ok=True)

    def close(self) -> None:
        self.db.close()
        self.http.close()
        self.lock.close()

    def disk_check(self) -> None:
        if shutil.disk_usage(self.root).free < self.min_free_bytes:
            raise OSError("Disk reserve reached; progress preserved")

    def request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(5):
            if endpoint != "/rate-limit":
                self.budget()  # Every attempt, including retries with an ambiguous outcome.
            self.disk_check()
            self.limiter.acquire()
            with self.db:
                row = self.db.execute(
                    "INSERT INTO requests(at,endpoint) VALUES (?,?)", (now(), endpoint)
                ).lastrowid
            try:
                response = self.http.get(
                    self.settings.openalex_base_url + endpoint,
                    params={
                        **params,
                        "api_key": self.settings.openalex_api_key,
                        "mailto": self.settings.openalex_mailto,
                    },
                )
            except httpx.TransportError:
                if attempt == 4:
                    raise RuntimeError("OpenAlex transport failure; resume saved cursor") from None
                time.sleep(2**attempt)
                continue
            cost = response.headers.get("x-ratelimit-cost-required-usd")
            with self.db:
                self.db.execute(
                    "UPDATE requests SET status=?,cost_usd=? WHERE id=?",
                    (response.status_code, cost, row),
                )
            if response.status_code == 429:
                if endpoint == "/rate-limit":
                    raise WaitingQuota("Budget endpoint unavailable (429); collection disabled")
                self.budget()  # Quota exhaustion stops; transient rate limiting may back off.
                if attempt == 4:
                    raise RuntimeError("OpenAlex rate-limit retries exhausted; resume cursor")
                try:
                    delay = float(response.headers.get("Retry-After", 2**attempt))
                except ValueError:
                    delay = float(2**attempt)
                time.sleep(min(60, max(0, delay)))
                continue
            if response.status_code in {500, 502, 503, 504} and attempt < 4:
                try:
                    delay = float(response.headers.get("Retry-After", 2**attempt))
                except ValueError:
                    delay = float(2**attempt)
                time.sleep(min(60, max(0, delay)))
                continue
            if response.status_code != 200:
                raise RuntimeError(f"OpenAlex HTTP {response.status_code}; progress preserved")
            body: dict[str, Any] = response.json()
            if endpoint != "/rate-limit":
                observed_cost = body.get("meta", {}).get("cost_usd")
                if observed_cost is not None:
                    with self.db:
                        self.db.execute(
                            "UPDATE requests SET cost_usd=? WHERE id=?", (str(observed_cost), row)
                        )
            return body
        raise RuntimeError("OpenAlex retries exhausted")

    def budget(self) -> dict[str, Any]:
        body = self.request("/rate-limit", {})
        quota = body.get("rate_limit", {})
        # Persist only known accounting fields, never identity/key fields.
        allowed = (
            "daily_budget_usd",
            "daily_used_usd",
            "daily_remaining_usd",
            "prepaid_balance_usd",
            "resets_at",
            "resets_in_seconds",
            "endpoint_costs_usd",
        )
        safe = {k: quota[k] for k in allowed if k in quota}
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('initial_budget',?)",
                (json.dumps({"at": now(), **safe}),),
            )
            self.db.execute(
                "INSERT OR REPLACE INTO metadata VALUES ('budget',?)",
                (json.dumps({"at": now(), **safe}),),
            )
        try:
            remaining = Decimal(str(quota["daily_remaining_usd"]))
            cost = Decimal(str(quota["endpoint_costs_usd"]["list"]))
        except (KeyError, TypeError):
            raise RuntimeError("Unknown free budget schema; collection disabled") from None
        if cost <= 0 or remaining < cost:
            raise WaitingQuota("Free daily budget insufficient; see budget.resets_at")
        return safe

    def cache_path(self, kind: str, cursor: str) -> Path:
        key = hashlib.sha256(f"{kind}:{cursor}".encode()).hexdigest()
        return self.root / "pages" / f"{key}.json"

    def consume(self, kind: str, cursor: str, envelope: dict[str, Any]) -> None:
        if envelope["kind"] != kind or envelope["cursor"] != cursor:
            raise ValueError("Page cache identity mismatch")
        page = envelope["body"]
        records = page["results"]
        meta = page["meta"]
        next_cursor = meta["next_cursor"]
        if not isinstance(records, list) or len(records) > 100:
            raise ValueError("Invalid page size")
        if next_cursor is not None and (not isinstance(next_cursor, str) or not next_cursor):
            raise ValueError("Invalid next cursor")
        if next_cursor and (
            next_cursor == cursor
            or self.db.execute(
                "SELECT 1 FROM pages WHERE kind=? AND cursor=?", (kind, next_cursor)
            ).fetchone()
        ):
            raise ValueError("Cursor cycle; refusing false completion")
        for record in records:
            if not isinstance(record.get("id"), str) or not record["id"].startswith(
                "https://openalex.org/" + ("A" if kind == "authors" else "I")
            ):
                raise ValueError("Invalid OpenAlex ID")
            ru = (
                any(
                    str(i.get("country_code") or "").lower() == "ru"
                    for i in record.get("last_known_institutions") or []
                )
                if kind == "authors"
                else str(record.get("country_code", "")).lower() == "ru"
            )
            if not ru:
                raise ValueError("Record outside Russian affiliation filter")
        digest = hashlib.sha256(self.cache_path(kind, cursor).read_bytes()).hexdigest()
        with self.db:
            for record in records:
                candidate = kind == "authors" and passes_heuristic(
                    record, self.settings, current_year=self.year
                )
                self.db.execute(
                    "INSERT OR REPLACE INTO records VALUES (?,?,?,?)",
                    (kind, record["id"], json.dumps(record, ensure_ascii=False), candidate),
                )
            self.db.execute(
                "INSERT INTO pages VALUES (?,?,?,?,?,?,?)",
                (
                    kind,
                    cursor,
                    next_cursor,
                    digest,
                    len(records),
                    meta["count"],
                    envelope["fetched_at"],
                ),
            )
            self.db.execute(
                "UPDATE state SET cursor=?,done=? WHERE kind=?",
                (next_cursor, next_cursor is None, kind),
            )

    def verify(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for kind in FILTERS:
            cursor: str | None = "*"
            visited: set[str] = set()
            total = 0
            ids: set[str] = set()
            page_cost = Decimal(0)
            while cursor is not None:
                row = self.db.execute(
                    "SELECT next_cursor,sha256,records FROM pages WHERE kind=? AND cursor=?",
                    (kind, cursor),
                ).fetchone()
                if row is None:
                    break
                if cursor in visited:
                    raise ValueError("Stored cursor cycle")
                visited.add(cursor)
                raw = self.cache_path(kind, cursor).read_bytes()
                if hashlib.sha256(raw).hexdigest() != row[1]:
                    raise ValueError("Saved page checksum mismatch")
                envelope = json.loads(raw)
                body = envelope["body"]
                if (
                    envelope["kind"] != kind
                    or envelope["cursor"] != cursor
                    or body["meta"]["next_cursor"] != row[0]
                    or len(body["results"]) != row[2]
                ):
                    raise ValueError("Saved page disagrees with manifest")
                ids.update(record["id"] for record in body["results"])
                page_cost += Decimal(str(body["meta"].get("cost_usd", 0)))
                total += row[2]
                cursor = row[0]
            state = self.db.execute(
                "SELECT cursor,done FROM state WHERE kind=?", (kind,)
            ).fetchone()
            if state != (cursor, int(cursor is None)):
                raise ValueError("Cursor chain disagrees with checkpoint")
            count = self.db.execute("SELECT COUNT(*) FROM pages WHERE kind=?", (kind,)).fetchone()[
                0
            ]
            if count != len(visited):
                raise ValueError("Unreachable saved pages")
            unique = self.db.execute(
                "SELECT COUNT(*) FROM records WHERE kind=?", (kind,)
            ).fetchone()[0]
            registered_ids = {
                value
                for (value,) in self.db.execute("SELECT id FROM records WHERE kind=?", (kind,))
            }
            if ids != registered_ids:
                raise ValueError("Registered IDs disagree with saved pages")
            counts = self.db.execute(
                "SELECT MIN(api_count),MAX(api_count) FROM pages WHERE kind=?", (kind,)
            ).fetchone()
            result[kind] = {
                "complete": cursor is None,
                "pages": count,
                "rows": total,
                "unique": unique,
                "duplicates": total - unique,
                "saved_pages_cost_usd": str(page_cost),
                "api_count_min": counts[0],
                "api_count_max": counts[1],
            }
        return result

    @classmethod
    def inspect(cls, root: Path) -> dict[str, Any]:
        """Verify a consistent read-only SQLite snapshot, including during collection."""
        instance = cls.__new__(cls)
        instance.root = root
        instance.db = sqlite3.connect(f"file:{root / 'registry.sqlite3'}?mode=ro", uri=True)
        try:
            instance.db.execute("BEGIN")
            return instance.snapshot("verified_local", persist=False)
        finally:
            instance.db.close()

    def snapshot(self, status: str, *, persist: bool = True) -> dict[str, Any]:
        report = self.verify()
        report.update(
            {
                "status": status,
                "at": now(),
                "root": str(self.root.resolve()),
                "candidates": self.db.execute(
                    "SELECT COUNT(*) FROM records WHERE candidate=1"
                ).fetchone()[0],
                "requests": self.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0],
                "requests_by_endpoint": dict(
                    self.db.execute("SELECT endpoint,COUNT(*) FROM requests GROUP BY endpoint")
                ),
                "known_list_cost_usd": str(
                    sum(
                        (
                            Decimal(v)
                            for (v,) in self.db.execute(
                                "SELECT cost_usd FROM requests WHERE endpoint != '/rate-limit' "
                                "AND cost_usd IS NOT NULL"
                            )
                        ),
                        Decimal(0),
                    )
                ),
                "unknown_outcomes": self.db.execute(
                    "SELECT COUNT(*) FROM requests WHERE status IS NULL"
                ).fetchone()[0],
                "bytes": sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file()),
                "free_bytes": shutil.disk_usage(self.root).free,
                "metadata": {
                    k: json.loads(v) for k, v in self.db.execute("SELECT key,value FROM metadata")
                },
            }
        )
        if persist:
            atomic_json(self.root / "status.json", report)
        return report

    def run(self) -> dict[str, Any]:
        self.verify()
        try:
            for kind in FILTERS:
                while True:
                    cursor, done = self.db.execute(
                        "SELECT cursor,done FROM state WHERE kind=?", (kind,)
                    ).fetchone()
                    if done:
                        break
                    self.disk_check()
                    cache = self.cache_path(kind, cursor)
                    if cache.exists():
                        envelope = json.loads(cache.read_text())
                    else:
                        page = self.request(
                            f"/{kind}", {"filter": FILTERS[kind], "per_page": 100, "cursor": cursor}
                        )
                        envelope = {
                            "kind": kind,
                            "cursor": cursor,
                            "fetched_at": now(),
                            "body": page,
                        }
                        atomic_json(cache, envelope)
                    self.consume(kind, cursor, envelope)
                    # Cheap progress; full checksum verification happens at run boundaries.
                    print(
                        json.dumps(
                            {
                                "at": now(),
                                "kind": kind,
                                "records": len(envelope["body"]["results"]),
                                "done": envelope["body"]["meta"]["next_cursor"] is None,
                            }
                        ),
                        flush=True,
                    )
            return self.snapshot("complete")
        except WaitingQuota:
            return self.snapshot("waiting_quota")
        except KeyboardInterrupt:
            return self.snapshot("interrupted")
