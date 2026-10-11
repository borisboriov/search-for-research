"""Shared immutable private storage and frozen profile contract."""

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIELDS = (
    "personal_contact",
    "coordinator_contact",
    "supervision_history",
    "published_recruitment",
    "direct_willingness",
    "topic",
    "supervisor_role",
    "student_level",
    "student_year",
    "required_skills",
    "external_students",
    "thesis_possible",
    "city",
    "work_format",
    "workload",
    "payment",
    "deadline",
    "response_method",
)


STATUSES = (
    "found",
    "not_found",
    "not_checked",
    "inaccessible",
    "contradiction",
    "explicit_negative",
)


ORCID_API = "https://pub.orcid.org/v3.0"


def now() -> str:
    return datetime.now(UTC).isoformat()


def ensure_not_stopped(root: Path) -> None:
    """STOP общего эксперимента действует и на новые вложенные попытки."""
    resolved = root.resolve()
    if any((parent / "stopped.json").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError("STOP root: новые source/model jobs запрещены")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: Any) -> None:
    """Не перезаписывать снимки и результаты, даже при повторном запуске."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".enrichment-write-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Атомарно публикует завершённый файл, FileExistsError сохраняет старый.
        # replace/rename могли бы перезаписать уже сохранённое доказательство.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def private_root(path: Path) -> Path:
    path = path.resolve()
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            raise ValueError("Исходные материалы и контакты должны находиться вне git")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def verified_sample(root: Path) -> list[dict[str, Any]]:
    if sha(root / "sample.json") != read(root / "manifest.json")["sample_sha256"]:
        raise ValueError("Замороженная выборка изменена")
    return list(read(root / "sample.json"))


def orcid_id(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"(?:https?://orcid.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", value)
    if not match:
        raise ValueError("Некорректный ORCID, запрос не отправлен")
    return match[1]


def public_candidates(record: dict[str, Any]) -> dict[str, Any]:
    person = record.get("person") or {}
    return {
        "name": person.get("name"),
        "other_names": person.get("other-names"),
        "emails": [
            entry
            for entry in (person.get("emails") or {}).get("email", [])
            if str(entry.get("visibility", "")).lower() == "public" and entry.get("email")
        ],
        "links": [
            entry
            for entry in (person.get("researcher-urls") or {}).get("researcher-url", [])
            if str(entry.get("visibility", "")).lower() == "public"
        ],
        "activities": record.get("activities-summary"),
        "record_last_modified": (record.get("history") or {}).get("last-modified-date"),
        "identity_verdict": "not_checked",
        "warning": "OpenAlex ORCID is a candidate; verify name and independent identity signal",
    }
