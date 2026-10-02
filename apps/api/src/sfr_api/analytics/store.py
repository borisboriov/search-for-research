"""Fsync-first disk journal and idempotent PostgreSQL replay.

An accepted event is a durable file, not a promise about an in-memory queue.
Completed files become retained compressed archives; corrupt files are quarantined.
No raw payload/driver exception is logged (driver messages can contain parameters).
"""

import fcntl
import gzip
import json
import logging
import os
import shutil
import stat
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DataError, IntegrityError

from sfr_api.analytics.models import Context, EventContext, ProductEvent, Search
from sfr_api.analytics.records import JournalEvent, SearchRecord

log = logging.getLogger(__name__)


class StorageUnavailable(OSError):
    """No durable acknowledgement is possible."""


def engine_for(url: str) -> Engine:
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("Analytics requires PostgreSQL with Psycopg 3")
    return create_engine(
        url,
        pool_size=2,
        max_overflow=0,
        pool_timeout=1,
        pool_recycle=300,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 1,
            "options": "-c timezone=UTC -c statement_timeout=1000 -c lock_timeout=500",
        },
    )


def _sync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    # A partially written file is retained for operator diagnosis.
    with os.fdopen(fd, "wb") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)
    _sync_dir(path.parent)


def _stat(path: Path) -> os.stat_result:
    try:
        return path.stat()
    except FileNotFoundError:
        # Replay may have archived this file between directory snapshot/stat.
        return os.stat_result((0,) * 10)


class DurableStore:
    def __init__(
        self,
        url: str,
        spool_dir: Path,
        *,
        max_bytes: int = 512 * 1024 * 1024,
        reserve_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        self.root = spool_dir
        self.max_bytes = max_bytes
        self.reserve_bytes = reserve_bytes
        self.max_pending_files = 10000
        self.engine = engine_for(url)
        self._locks = {"journal": threading.Lock(), "replay": threading.Lock()}
        # Awaiter cancellation does not stop a synchronous disk worker. Admission
        # therefore belongs to the actual operation, not its HTTP awaiter/timeout.
        self._append_limit = 2
        self._append_admission = threading.BoundedSemaphore(self._append_limit)
        self._append_state_lock = threading.Lock()
        self._append_inflight = 0
        self._append_rejected = 0
        for name in ("", "pending", "archive", "quarantine"):
            path = spool_dir / name
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(path, stat.S_IRWXU)
        self.status_path = self.root / "status.json"

    @contextmanager
    def _exclusive(self, name: str = "journal"):  # type: ignore[no-untyped-def]
        with self._locks[name], (self.root / f"{name}.lock").open("a", encoding="utf-8") as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def append(self, kind: str, records: list[dict[str, Any]]) -> None:
        if not self._append_admission.acquire(blocking=False):
            with self._append_state_lock:
                self._append_rejected += 1
            # Do not write diagnostics to the stalled disk on this rejection.
            # The category is logged and the safe in-memory count is exposed.
            log.error("analytics storage failure category=writer_busy")
            raise StorageUnavailable("analytics writers are occupied")
        with self._append_state_lock:
            self._append_inflight += 1
        try:
            self._append(kind, records)
        except UnicodeEncodeError:
            # Encoding failure is not a durable write and must not leak the
            # offending string through exception chaining or diagnostics.
            log.error("analytics storage failure category=encoding")
            raise StorageUnavailable("analytics record encoding failed") from None
        finally:
            # This runs in the physical worker, even after its HTTP awaiter has
            # timed out. No later request can reuse the slot prematurely.
            with self._append_state_lock:
                self._append_inflight -= 1
            self._append_admission.release()

    def _append(self, kind: str, records: list[dict[str, Any]]) -> None:
        envelope = {"version": 1, "kind": kind, "records": records}
        content = json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode("utf-8")
        with self._exclusive():
            paths = list((self.root / "pending").iterdir())
            pending = sum(_stat(p).st_size for p in paths)
            free = shutil.disk_usage(self.root).free
            if (
                pending + len(content) > self.max_bytes
                or len(paths) >= self.max_pending_files
                or free - len(content) < self.reserve_bytes
            ):
                self._failure("capacity")
                raise StorageUnavailable("analytics journal capacity exhausted")
            try:
                _atomic(self.root / "pending" / f"{uuid4()}.json", content)
            except OSError:
                self._failure("disk_write")
                raise StorageUnavailable("analytics journal write failed") from None

    def _status(self) -> dict[str, Any]:
        try:
            value = json.loads(self.status_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _failure(self, category: str) -> None:
        log.error("analytics storage failure category=%s", category)
        status = self._status()
        status["last_error"] = category
        status["last_error_at"] = datetime.now(UTC).isoformat()
        status["error_count"] = status.get("error_count", 0) + 1
        try:
            _atomic(self.status_path, json.dumps(status).encode())
        except OSError:
            log.error("analytics diagnostics write failed")

    def diagnostics(self) -> dict[str, Any]:
        result = self._status()
        with self._append_state_lock:
            result["append_inflight"] = self._append_inflight
            result["append_rejected"] = self._append_rejected
            result["append_limit"] = self._append_limit
        for name in ("pending", "archive", "quarantine"):
            paths = list((self.root / name).iterdir())
            result[f"{name}_count"] = len(paths)
            result[f"{name}_bytes"] = sum(_stat(path).st_size for path in paths)
        pending_paths = list((self.root / "pending").iterdir())
        oldest = min((_stat(p).st_mtime for p in pending_paths), default=None)
        result["oldest_pending_at"] = (
            datetime.fromtimestamp(oldest, UTC).isoformat() if oldest else None
        )
        result["oldest_pending_age_seconds"] = (
            (datetime.now(UTC).timestamp() - oldest) if oldest else 0
        )
        result["free_bytes"] = shutil.disk_usage(self.root).free
        result["max_pending_bytes"] = self.max_bytes
        result["reserve_bytes"] = self.reserve_bytes
        result["max_pending_files"] = self.max_pending_files
        result["incomplete"] = bool(
            result["quarantine_count"] or result.get("error_count") or result["append_rejected"]
        )
        return result

    def replay(self, limit: int = 100) -> dict[str, int]:
        result = {"persisted": 0, "quarantined": 0, "errors": 0}
        with self._exclusive("replay"):
            # A crashed unacknowledged write remains evidence; do not parse a
            # file that another writer may still be filling. Quarantine stale
            # temporary files after a minute, without losing their bytes.
            for temporary in (self.root / "pending").glob("*.tmp"):
                if datetime.now(UTC).timestamp() - _stat(temporary).st_mtime > 60:
                    os.replace(temporary, self.root / "quarantine" / temporary.name)
                    _sync_dir(self.root / "pending")
                    _sync_dir(self.root / "quarantine")
                    self._failure("unfinished_write")
                    result["quarantined"] += 1
            paths = sorted(
                (self.root / "pending").glob("*.json"), key=lambda p: p.stat().st_mtime_ns
            )
            for path in paths[:limit]:
                try:
                    envelope = json.loads(path.read_text(encoding="utf-8"))
                    self._validate(envelope)
                except (OSError, ValueError, TypeError, KeyError, AttributeError):
                    os.replace(path, self.root / "quarantine" / path.name)
                    _sync_dir(self.root / "pending")
                    _sync_dir(self.root / "quarantine")
                    self._failure("corrupt_record")
                    result["quarantined"] += 1
                    continue
                try:
                    self._persist(envelope)
                except (DataError, IntegrityError):
                    # PG data/integrity errors cannot heal by retrying the same
                    # immutable bytes (e.g. NUL in Text/JSONB). Preserve the full
                    # record and allow later independent records to proceed.
                    os.replace(path, self.root / "quarantine" / path.name)
                    _sync_dir(self.root / "pending")
                    _sync_dir(self.root / "quarantine")
                    self._failure("database_record")
                    result["quarantined"] += 1
                    continue
                except Exception:
                    self._failure("database")
                    result["errors"] += 1
                    break
                try:
                    # Archive is durable BEFORE removing the pending copy. A crash in
                    # between simply replays the same PKs and replaces the same archive.
                    archive = self.root / "archive" / f"{path.stem}.json.gz"
                    _atomic(archive, gzip.compress(path.read_bytes(), mtime=0))
                    path.unlink()
                    _sync_dir(path.parent)
                    status = self._status()
                    status["last_success"] = datetime.now(UTC).isoformat()
                    status["last_error"] = None
                    _atomic(self.status_path, json.dumps(status).encode())
                    result["persisted"] += len(envelope["records"])
                except OSError:
                    self._failure("archive_write")
                    result["errors"] += 1
                    break
        return result

    @staticmethod
    def _validate(envelope: dict[str, Any]) -> None:
        if not isinstance(envelope, dict):
            raise ValueError("invalid journal envelope")
        if envelope.get("version") != 1 or envelope.get("kind") not in {"search", "events"}:
            raise ValueError("unknown journal contract")
        records = envelope["records"]
        if not isinstance(records, list) or not records or len(records) > 10:
            raise ValueError("invalid journal batch")
        for record in records:
            parsed = (
                JournalEvent.model_validate(record)
                if envelope["kind"] == "events"
                else SearchRecord.model_validate(record)
            )
            if not parsed.consistent():
                raise ValueError("journal identifier mismatch")

    def _persist(self, envelope: dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            for record in envelope["records"]:
                if envelope["kind"] == "events":
                    event = {
                        key: value for key, value in record.items() if key != "private_context"
                    }
                    inserted = connection.execute(
                        insert(ProductEvent)
                        .values(**event)
                        .on_conflict_do_nothing()
                        .returning(ProductEvent.event_id)
                    ).first()
                    if inserted:
                        connection.execute(insert(EventContext).values(**record["private_context"]))
                else:
                    inserted = connection.execute(
                        insert(Search)
                        .values(**record["search"])
                        .on_conflict_do_nothing()
                        .returning(Search.search_id)
                    ).first()
                    if inserted:
                        connection.execute(insert(Context).values(**record["context"]))
