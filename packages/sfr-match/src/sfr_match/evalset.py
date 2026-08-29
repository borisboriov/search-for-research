"""Golden set and judgments: loading and validation.

Both files live in git (``packages/sfr-match/eval/``) — they are a project asset,
not a build artefact (SPEC_SFR1 §2).
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

QueryKind = Literal["in-domain", "edge", "out-of-domain"]

_ENV_EVAL_DIR = "SFR_MATCH_EVAL_DIR"


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
