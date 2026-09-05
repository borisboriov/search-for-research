"""Request/response contract of the API.

Product decision (MVP plan v1.3): supervisor cards are open and free — the API
returns the whole card without authentication. Monetisation lands on services
built around the data, not on the data itself.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# Словесный грейд совпадения на карточке (SPEC_SFR4 §0.9): границы шкалы живут
# в настройках API (score_weak/score_high) и отдаются в /health — фронт сам
# порогов не знает и не дублирует.
Grade = Literal["high", "medium", "low"]

# Уверенность всей выдачи по top-1: none — «уверенных совпадений нет» (ниже
# score_threshold), weak — серая зона (ниже score_weak), ok — обычная выдача.
Confidence = Literal["none", "weak", "ok"]


class TopWork(BaseModel):
    """One publication on the card: titles carry the signal (SFR-2), so title first."""

    title: str
    year: int | None = None


class SupervisorCard(BaseModel):
    author_id: str
    name: str
    institution: str | None = None
    h_index: int | None = None
    works_count: int | None = None
    topics: list[str] = []
    profile_text: str

    # SFR-3 additions (§4 SPEC_SFR3). All optional: the search index does not
    # carry them — they come from the cards enrichment file (`sfr export cards`)
    # and default to empty when it is absent (tests, bare index).
    cited_by_count: int | None = None
    position: str | None = Field(
        default=None, description="Должность, если есть в данных каталога; сейчас в данных нет"
    )
    email: str | None = Field(
        default=None, description="Только из данных каталога, ничего не парсим; сейчас нет"
    )
    top_works: list[TopWork] = []
    serendipity: bool = Field(
        default=False,
        description="Зарезервировано: API пока не выставляет, фронт умеет рисовать",
    )

    @classmethod
    def from_doc(cls, doc: dict[str, Any], extra: dict[str, Any] | None = None) -> "SupervisorCard":
        extra = extra or {}
        return cls(
            author_id=str(doc["id"]),
            name=str(doc["name"]),
            institution=doc.get("institution"),
            h_index=doc.get("h_index"),
            works_count=doc.get("works_count"),
            topics=list(doc.get("topics") or []),
            profile_text=str(doc.get("display_text") or doc["profile_text"]),
            cited_by_count=extra.get("cited_by_count"),
            position=extra.get("position"),
            email=extra.get("email"),
            top_works=[TopWork(**w) for w in extra.get("top_works") or []],
        )


class MatchResult(SupervisorCard):
    score: float = Field(description="Cosine similarity with the query, 0..1")
    rank: int
    grade: Grade = Field(
        description="Словесный грейд для бейджа: high >= score_high, "
        "medium >= score_weak, ниже — low; границы в /health"
    )


class MatchRequest(BaseModel):
    # Жёсткая граница на уровне схемы — страховка от мегабайтных тел до входа
    # в сервис (REVIEW_SFR3 Medium). Человеческая валидация (3..500 символов
    # с текстом подсказки) остаётся в MatchService.validate.
    query: str = Field(min_length=3, max_length=2000)
    k: int | None = None


class MatchResponse(BaseModel):
    results: list[MatchResult]
    below_threshold: bool = Field(
        description="Top-1 score is under the cut-off: show 'no confident matches' — "
        "a warning above the results, not a refusal to show them. "
        "Эквивалент confidence == 'none'; оставлено для совместимости"
    )
    confidence: Confidence = Field(
        description="Уверенность выдачи по top-1: none < score_threshold, "
        "weak < score_weak (баннер «совпадения слабые»), иначе ok"
    )
    index_version: str
    took_ms: float


class SupervisorSummary(BaseModel):
    """One row of the catalogue listing — enough for a sitemap entry or a link."""

    author_id: str
    name: str
    institution: str | None = None


class SupervisorsPage(BaseModel):
    items: list[SupervisorSummary]
    next_cursor: str | None = Field(
        default=None, description="author_id to pass as ?cursor= for the next page; null = end"
    )
    total: int


class HealthResponse(BaseModel):
    status: str
    model: str
    index_version: str
    profiles_count: int
    score_threshold: float
    score_weak: float
    score_high: float
    search_backend: str
    compose: str
    built_at: str
    # Кэш ответов /match (SPEC_SFR4 §2): hit-rate — прямой сигнал, сколько
    # инференса сэкономлено на повторных запросах.
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
