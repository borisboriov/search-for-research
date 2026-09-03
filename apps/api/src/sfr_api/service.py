"""The thin layer between HTTP and ``sfr_match``: no search logic lives here.

Loading the model and the index is a one-off cost of the process (FRIDA takes
seconds); it happens in the lifespan and never on a request — see ``main.py``.
"""

import json
import time
from pathlib import Path
from typing import Any

from sfr_api.schemas import (
    HealthResponse,
    MatchResponse,
    MatchResult,
    SupervisorCard,
    SupervisorsPage,
    SupervisorSummary,
)
from sfr_api.settings import ApiSettings
from sfr_match.runtime import select_search_backend
from sfr_match.search import Backend, load_backend


class QueryError(ValueError):
    """A user-facing complaint about the query itself (mapped to 422)."""


def load_cards_extras(path: Path | None) -> dict[str, dict[str, Any]]:
    """Card enrichment (citations, top works) built offline by ``sfr export cards``.

    The file is optional by design: the search index stays the single mandatory
    artefact, and a missing enrichment degrades to empty card fields, not to a crash.
    """
    if path is None or not path.exists():
        return {}
    extras: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                extras[str(record["id"])] = record
    return extras


class MatchService:
    def __init__(
        self,
        backend: Backend,
        settings: ApiSettings,
        extras: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.backend = backend
        self.settings = settings
        self.by_id: dict[str, dict[str, Any]] = {str(doc["id"]): doc for doc in backend.docs}
        # Stable listing order for pagination: author_id is the natural key of the corpus.
        self.ordered_ids: list[str] = sorted(self.by_id)
        self.extras = extras if extras is not None else load_cards_extras(settings.cards_path)

    @classmethod
    def from_settings(cls, settings: ApiSettings) -> "MatchService":
        """Open the index named by settings; a missing index fails here, at startup."""
        index_dir: Path = settings.resolved_index_dir()
        if not (index_dir / "meta.json").exists():
            msg = (
                f"индекс не найден: {index_dir}. Собрать офлайн — `make index-sfr2` "
                "(или указать другой каталог в SFR_API_INDEX_DIR); API индекс не строит."
            )
            raise FileNotFoundError(msg)
        backend = load_backend(index_dir, settings.model)
        if settings.warmup:
            backend.warmup()
        return cls(backend, settings)

    def validate(self, query: str, k: int | None) -> tuple[str, int]:
        text = query.strip()
        low, high = self.settings.min_query_chars, self.settings.max_query_chars
        if len(text) < low:
            raise QueryError(
                f"Запрос слишком короткий: {len(text)} символов, нужно хотя бы {low}. "
                "Опишите тему научной работы своими словами."
            )
        if len(text) > high:
            raise QueryError(
                f"Запрос слишком длинный: {len(text)} символов, максимум {high}. "
                "Оставьте суть — тему и методы."
            )
        k = self.settings.default_k if k is None else k
        if k < 1 or k > self.settings.max_k:
            raise QueryError(f"k должно быть от 1 до {self.settings.max_k}, получено {k}.")
        return text, k

    def _card(self, doc: dict[str, Any]) -> SupervisorCard:
        return SupervisorCard.from_doc(doc, self.extras.get(str(doc["id"])))

    def match(self, query: str, k: int | None = None) -> MatchResponse:
        text, top_k = self.validate(query, k)
        started = time.perf_counter()
        hits = self.backend.search(text, k=top_k)
        took_ms = (time.perf_counter() - started) * 1000
        results = [
            MatchResult(
                **self._card(self.by_id[hit.author_id]).model_dump(),
                score=hit.score,
                rank=hit.rank,
            )
            for hit in hits
        ]
        top_score = results[0].score if results else 0.0
        return MatchResponse(
            results=results,
            below_threshold=top_score < self.settings.score_threshold,
            index_version=self.backend.meta.version,
            took_ms=round(took_ms, 1),
        )

    def card(self, author_id: str) -> SupervisorCard | None:
        doc = self.by_id.get(author_id)
        return None if doc is None else self._card(doc)

    def list_supervisors(self, limit: int, cursor: str | None = None) -> SupervisorsPage:
        """Keyset pagination over the fixed corpus: cursor = last author_id of the page."""
        start = 0
        if cursor is not None:
            # bisect would be O(log n), but 535 ids do not deserve the extra code.
            try:
                start = self.ordered_ids.index(cursor) + 1
            except ValueError as exc:
                raise QueryError(f"Неизвестный cursor: {cursor}.") from exc
        page_ids = self.ordered_ids[start : start + limit]
        items = [
            SupervisorSummary(
                author_id=author_id,
                name=str(self.by_id[author_id]["name"]),
                institution=self.by_id[author_id].get("institution"),
            )
            for author_id in page_ids
        ]
        has_more = start + limit < len(self.ordered_ids)
        return SupervisorsPage(
            items=items,
            next_cursor=page_ids[-1] if has_more and page_ids else None,
            total=len(self.ordered_ids),
        )

    def health(self) -> HealthResponse:
        meta = self.backend.meta
        return HealthResponse(
            status="ok",
            model=meta.hf_id or meta.model_key,
            index_version=meta.version,
            profiles_count=meta.n_profiles,
            score_threshold=self.settings.score_threshold,
            search_backend=select_search_backend(),
            compose=meta.compose,
            built_at=meta.built_at,
        )
