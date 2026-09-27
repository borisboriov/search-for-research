"""Golden set and judgments: loading and validation.

Both files live in git (``packages/sfr-match/eval/``) — they are a project asset,
not a build artefact (SPEC_SFR1 §2).
"""

import hashlib
import json
import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

QueryKind = Literal["in-domain", "edge", "out-of-domain"]

_ENV_EVAL_DIR = "SFR_MATCH_EVAL_DIR"

# Named query sets. They live in separate files on purpose: SFR-1 metrics are
# computed over ``golden`` alone, and growing that file would silently move
# already-published numbers (nDCG is computed against the judged pool).
QUERY_SETS = {
    "golden": "queries.jsonl",  # SFR-1 golden set, frozen at 30 queries
    "ood": "ood_queries.jsonl",  # SFR-2 out-of-domain set for threshold calibration
    "external": "external_queries.jsonl",  # queries collected from real students
}


def eval_dir() -> Path:
    """Directory holding queries/judgments — ``packages/sfr-match/eval``.

    Resolved from the module location (the workspace is installed editable), with
    an env override for anyone running from a wheel.
    """
    override = os.environ.get(_ENV_EVAL_DIR)
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "eval"


class Query(BaseModel):
    id: str
    text: str = Field(min_length=3)
    expect: QueryKind
    comment: str = ""
    # Who wrote the query: "" for the sets written by the agent, "student" for the
    # external set (SPEC_SFR2 §6). Declared explicitly — pydantic drops unknown keys.
    source: str = ""

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query id must not be blank")
        return value


class Judgment(BaseModel):
    query_id: str
    author_id: str
    grade: int = Field(ge=0, le=2)
    rationale: str = ""
    # Какая итерация поставила оценку (SFR-5). Нужно, чтобы выборка на ручную
    # проверку бралась именно из новой партии: пул растёт, и без метки 20 пар
    # разбавляются оценками, которые человек уже смотрел в прошлые разы.
    # Необязательное: строки прошлых итераций читаются с пустым значением.
    iteration: str = ""
    # Кто поставил оценку: модель и способ («fable (sfr-judge)»). Объявлено явно,
    # иначе pydantic молча выбросит поле, и по файлу нельзя будет сказать, чьи это
    # оценки — а с SFR-5c пары судит отдельный субагент, а не сессия (SFR-5c §6).
    judge: str = ""
    # #123: отпечаток профиля, по которому ставилась оценка (`profile_fingerprint`
    # его `profile_text`). После склейки у канонического id другой профиль, и
    # старая оценка к нему не относится: метрики такие пары считают
    # неоценёнными, а не берут устаревшую оценку молча. Пусто — строка до #123,
    # сверить не с чем.
    profile_fp: str = ""


def _iter_jsonl(path: Path) -> Iterator[dict[str, object]]:
    if not path.exists():
        msg = f"{path} not found — golden set and judgments are versioned in git"
        raise FileNotFoundError(msg)
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON ({exc})") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{lineno}: expected a JSON object")
            yield record


def query_set_path(name: str) -> Path:
    """Resolve a query-set name to its file; unknown names fail loudly."""
    if name not in QUERY_SETS:
        raise ValueError(f"unknown query set {name!r}; known: {', '.join(QUERY_SETS)}")
    return eval_dir() / QUERY_SETS[name]


def load_queries(path: Path | None = None) -> list[Query]:
    """Parse and validate ``queries.jsonl``; ids must be unique."""
    path = path or (eval_dir() / "queries.jsonl")
    queries = [Query.model_validate(record) for record in _iter_jsonl(path)]
    seen: set[str] = set()
    for query in queries:
        if query.id in seen:
            raise ValueError(f"{path}: duplicate query id {query.id!r}")
        seen.add(query.id)
    return queries


def profile_fingerprint(profile_text: str) -> str:
    """Отпечаток профиля для строки оценки (#123): 16 hex от sha256 текста."""
    return hashlib.sha256(profile_text.encode("utf-8")).hexdigest()[:16]


def split_stale(
    judgments: Mapping[tuple[str, str], Judgment], fingerprints: Mapping[str, str]
) -> tuple[dict[tuple[str, str], Judgment], dict[str, int], list[tuple[str, str]]]:
    """Отделить оценки, профиль которых изменился после судейства (#123).

    ``fingerprints`` — отпечатки текущих профилей (id → отпечаток). Оценка с
    отпечатком, который не совпал с текущим профилем, **устарела** — её нет в
    результате, пара считается неоценённой. Оценка без отпечатка (строки до
    #123) остаётся: сверить не с чем, это «без отпечатка», а не «устарела».
    Возвращает (годные оценки, счётчики, ключи устаревших).
    """
    usable: dict[tuple[str, str], Judgment] = {}
    counts = {"fresh": 0, "stale": 0, "no_fingerprint": 0}
    stale: list[tuple[str, str]] = []
    for key, judgment in judgments.items():
        current = fingerprints.get(key[1])
        if not judgment.profile_fp:
            counts["no_fingerprint"] += 1
            usable[key] = judgment
        elif current is not None and current != judgment.profile_fp:
            counts["stale"] += 1
            stale.append(key)
        else:
            counts["fresh"] += 1
            usable[key] = judgment
    return usable, counts, sorted(stale)


def load_judgments(path: Path | None = None) -> dict[tuple[str, str], Judgment]:
    """Parse and validate ``judgments.jsonl``; (query_id, author_id) must be unique."""
    path = path or (eval_dir() / "judgments.jsonl")
    judgments: dict[tuple[str, str], Judgment] = {}
    for record in _iter_jsonl(path):
        judgment = Judgment.model_validate(record)
        key = (judgment.query_id, judgment.author_id)
        if key in judgments:
            raise ValueError(f"{path}: duplicate judgment for {key}")
        judgments[key] = judgment
    return judgments


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    """Write JSONL with readable Cyrillic (``ensure_ascii=False``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
