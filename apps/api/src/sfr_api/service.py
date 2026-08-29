"""The thin layer between HTTP and ``sfr_match``: no search logic lives here.

Loading the model and the index is a one-off cost of the process (FRIDA takes
seconds); it happens in the lifespan and never on a request — see ``main.py``.
"""

import time
from pathlib import Path
from typing import Any

from sfr_api.schemas import HealthResponse, MatchResponse, MatchResult, SupervisorCard
from sfr_api.settings import ApiSettings
from sfr_match.runtime import select_search_backend
from sfr_match.search import Backend, load_backend


class QueryError(ValueError):
    """A user-facing complaint about the query itself (mapped to 422)."""


class MatchService:
    def __init__(self, backend: Backend, settings: ApiSettings) -> None:
        self.backend = backend
        self.settings = settings
        self.by_id: dict[str, dict[str, Any]] = {str(doc["id"]): doc for doc in backend.docs}

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

    def match(self, query: str, k: int | None = None) -> MatchResponse:
        text, top_k = self.validate(query, k)
        started = time.perf_counter()
        hits = self.backend.search(text, k=top_k)
        took_ms = (time.perf_counter() - started) * 1000
        results = [
            MatchResult(
                **SupervisorCard.from_doc(self.by_id[hit.author_id]).model_dump(),
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
        return None if doc is None else SupervisorCard.from_doc(doc)

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
