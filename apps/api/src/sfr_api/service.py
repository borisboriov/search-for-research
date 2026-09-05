"""The thin layer between HTTP and ``sfr_match``: no search logic lives here.

Loading the model and the index is a one-off cost of the process (FRIDA takes
seconds); it happens in the lifespan and never on a request — see ``main.py``.
"""

import json
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from sfr_api.schemas import (
    Confidence,
    Grade,
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
        # LRU-кэш ответов /match (SPEC_SFR4 §2). Замок обязателен: match идёт
        # в threadpool, одновременных потоков — match_concurrency.
        self._cache: OrderedDict[tuple[str, int], tuple[float, MatchResponse]] = OrderedDict()
        self._cache_lock = threading.Lock()
        self.cache_hits = 0
        self.cache_misses = 0

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

    def _grade(self, score: float) -> Grade:
        """Словесный грейд бейджа; границы — в settings, фронт их не дублирует."""
        if score >= self.settings.score_high:
            return "high"
        if score >= self.settings.score_weak:
            return "medium"
        return "low"

    def _confidence(self, top_score: float) -> Confidence:
        """Уверенность выдачи по top-1 (SPEC_SFR4 §0.9: серая зона порога)."""
        if top_score < self.settings.score_threshold:
            return "none"
        if top_score < self.settings.score_weak:
            return "weak"
        return "ok"

    def match_cached(self, query: str, k: int | None = None) -> tuple[MatchResponse, bool]:
        """Match with the LRU cache in front; returns (response, cache_hit).

        The key is the normalised query text + k — repeated queries are the
        cheapest capacity FRIDA can get (~2 rps of raw encode on CPU). The
        corpus is fixed, so a hit can only go stale by TTL, not by content.
        """
        text, top_k = self.validate(query, k)
        key = (" ".join(text.lower().split()), top_k)
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] < self.settings.match_cache_ttl_seconds:
                self._cache.move_to_end(key)
                self.cache_hits += 1
                # took_ms — время поиска; из кэша поиск не выполнялся
                return entry[1].model_copy(update={"took_ms": 0.0}), True
            self.cache_misses += 1
        response = self.match(query, k)
        with self._cache_lock:
            self._cache[key] = (now, response)
            self._cache.move_to_end(key)
            while len(self._cache) > self.settings.match_cache_max_entries:
                self._cache.popitem(last=False)
        return response, False

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
                grade=self._grade(hit.score),
            )
            for hit in hits
        ]
        top_score = results[0].score if results else 0.0
        confidence = self._confidence(top_score)
        return MatchResponse(
            results=results,
            below_threshold=confidence == "none",
            confidence=confidence,
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
        lookups = self.cache_hits + self.cache_misses
        return HealthResponse(
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            cache_hit_rate=round(self.cache_hits / lookups, 3) if lookups else 0.0,
            status="ok",
            model=meta.hf_id or meta.model_key,
            index_version=meta.version,
            profiles_count=meta.n_profiles,
            score_threshold=self.settings.score_threshold,
            score_weak=self.settings.score_weak,
            score_high=self.settings.score_high,
            search_backend=select_search_backend(),
            compose=meta.compose,
            built_at=meta.built_at,
        )
