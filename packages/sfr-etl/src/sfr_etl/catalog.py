"""Отбор авторов вуза со стратификацией по областям OpenAlex (SPEC_SFR5 §2).

Почему не `works_count:desc` с лимитом, как в SFR-0. Сортировка по числу работ
поднимает наверх участников мегаколлабораций: у физика ATLAS тысячи статей, у
сильного экономиста — сотня. На корпусе 535 профилей это дало каталог, в котором
запрос «computer science backend engineering» находил физиков и химиков.

Отбор здесь двухслойный:

1. **Пул** — все авторы вуза, проходящие эвристику НР. Серверный фильтр OpenAlex
   умеет только пороги по works_count и h-index; условие свежести публикации
   применяется локально по ``counts_by_year`` (в API такого фильтра нет).
2. **Квота** — из пула берётся ``quota`` авторов, распределённых по областям
   (``topics[].field``) пропорционально размеру области в этом вузе, но с полом:
   маленькая область получает хотя бы ``floor`` мест, пока они у неё есть.
   Внутри области — по h-index, он меньше раздут соавторством, чем works_count.

Область автора — та, на которую приходится больше всего его тематической массы
(сумма ``count`` по темам области). Ничья решается по имени области, чтобы отбор
был воспроизводим.
"""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from sfr_core.heuristics import is_supervisor_candidate
from sfr_core.models import Institution
from sfr_core.settings import Settings
from sfr_etl.client import OpenAlexClient
from sfr_etl.ingest import last_publication_year, upsert_author

log = structlog.get_logger(__name__)

FIELD_UNKNOWN = "Без области"
DEFAULT_FIELD_FLOOR = 8


def primary_field(record: dict[str, Any]) -> str:
    """Область OpenAlex с наибольшей тематической массой автора."""
    mass: dict[str, float] = {}
    for topic in record.get("topics") or []:
        field = (topic.get("field") or {}).get("display_name")
        if not field:
            continue
        mass[field] = mass.get(field, 0.0) + float(topic.get("count") or 0)
    if not mass:
        return FIELD_UNKNOWN
    return max(sorted(mass), key=lambda name: mass[name])


def passes_heuristic(
    record: dict[str, Any], settings: Settings, *, current_year: int | None = None
) -> bool:
    """Полная эвристика НР, включая свежесть — серверный фильтр её не покрывает."""
    summary = record.get("summary_stats") or {}
    return is_supervisor_candidate(
        works_count=record.get("works_count") or 0,
        h_index=summary.get("h_index"),
        last_publication_year=last_publication_year(record.get("counts_by_year") or []),
        current_year=current_year or datetime.now(UTC).year,
        min_works=settings.supervisor_min_works,
        min_h_index=settings.supervisor_min_h_index,
        recent_years=settings.supervisor_recent_years,
    )


def allocate_quota(
    sizes: dict[str, int], quota: int, floor: int = DEFAULT_FIELD_FLOOR
) -> dict[str, int]:
    """Сколько мест отдать каждой области: пол + пропорция от остатка.

    Пол ограничен размером самой области, поэтому сумма полов не может превысить
    размер пула; если она превышает квоту, места раздаются по кругу от самых
    больших областей к самым маленьким — так квота не «съедается» хвостом
    из областей с одним автором.
    """
    total = sum(sizes.values())
    if total <= quota:
        return dict(sizes)

    order = sorted(sizes, key=lambda name: (-sizes[name], name))
    base = {name: min(sizes[name], floor) for name in order}
    if sum(base.values()) > quota:
        allotted = {name: 0 for name in order}
        left = quota
        while left > 0:
            progressed = False
            for name in order:
                if left == 0:
                    break
                if allotted[name] < sizes[name]:
                    allotted[name] += 1
                    left -= 1
                    progressed = True
            if not progressed:  # pragma: no cover — total > quota гарантирует места
                break
        return {name: n for name, n in allotted.items() if n}

    remaining = quota - sum(base.values())
    headroom = {name: sizes[name] - base[name] for name in order}
    pool = sum(headroom.values())
    extra = {name: 0 for name in order}
    if pool:
        for name in order:
            extra[name] = int(remaining * headroom[name] / pool)
        # Остаток от целочисленного деления — областям с наибольшим запасом.
        left = remaining - sum(extra.values())
        for name in sorted(order, key=lambda n: (-(headroom[n] - extra[n]), n)):
            if left == 0:
                break
            if extra[name] < headroom[name]:
                extra[name] += 1
                left -= 1
    return {name: base[name] + extra[name] for name in order if base[name] + extra[name]}


def _rank_key(record: dict[str, Any]) -> tuple[int, int, str]:
    summary = record.get("summary_stats") or {}
    return (
        -int(summary.get("h_index") or 0),
        -int(record.get("works_count") or 0),
        str(record.get("id") or ""),
    )


def stratified_select(
    records: Sequence[dict[str, Any]],
    *,
    quota: int,
    settings: Settings,
    floor: int = DEFAULT_FIELD_FLOOR,
    current_year: int | None = None,
    keep_ids: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Отобрать ``quota`` авторов из пула. Возвращает (записи, размеры областей).

    ``keep_ids`` — авторы, которые обязаны попасть в отбор (уже в каталоге:
    на них стоят судейские оценки и превью лендинга). Они занимают места внутри
    своих областей, а не добавляются сверх квоты.
    """
    eligible = [r for r in records if passes_heuristic(r, settings, current_year=current_year)]
    by_field: dict[str, list[dict[str, Any]]] = {}
    for record in eligible:
        by_field.setdefault(primary_field(record), []).append(record)
    for bucket in by_field.values():
        bucket.sort(key=_rank_key)

    sizes = {name: len(bucket) for name, bucket in by_field.items()}
    allocation = allocate_quota(sizes, quota, floor=floor)

    forced = {str(i) for i in keep_ids}
    selected: list[dict[str, Any]] = []
    for name, bucket in by_field.items():
        take = allocation.get(name, 0)
        must = [r for r in bucket if str(r["id"]).rsplit("/", 1)[-1] in forced]
        must_ids = {str(r["id"]) for r in must}
        rest = [r for r in bucket if str(r["id"]) not in must_ids]
        chosen = must + rest[: max(0, take - len(must))]
        selected.extend(chosen)
    selected.sort(key=_rank_key)
    return selected, sizes


def fetch_candidate_pool(
    client: OpenAlexClient, institution: Institution, settings: Settings
) -> list[dict[str, Any]]:
    """Все авторы вуза, проходящие серверные пороги эвристики НР.

    Без верхнего лимита по works_count (SPEC_SFR5 §2): пул — это то, из чего
    потом набирается квота, а не сам каталог. 200 записей на страницу, поэтому
    даже 6 500 авторов МГУ — это 33 запроса, целиком уходящих в дисковый кэш.
    """
    return list(
        client.paginate(
            "/authors",
            {
                "filter": (
                    f"last_known_institutions.id:{institution.openalex_id},"
                    f"works_count:>{settings.supervisor_min_works - 1},"
                    f"summary_stats.h_index:>{settings.supervisor_min_h_index - 1}"
                ),
                "sort": "works_count:desc",
            },
        )
    )


def home_institution_id(
    record: dict[str, Any], catalogue: dict[str, int], fallback_db_id: int
) -> int:
    """Какой вуз показывать на карточке автора, аффилированного с несколькими.

    OpenAlex отдаёт ``last_known_institutions`` списком, и человек из МФТИ,
    работающий ещё и в МИФИ, попадает в пулы обоих вузов. Брать «тот вуз, чей
    ингест выполнялся последним» нельзя: аффилиация начинает зависеть от порядка
    команд. Берём первый вуз из списка автора, который есть в нашем каталоге —
    решение детерминированное и не зависит от порядка прогонов.
    """
    for entry in record.get("last_known_institutions") or []:
        short = str(entry.get("id") or "").rsplit("/", 1)[-1]
        if short in catalogue:
            return catalogue[short]
    return fallback_db_id


def ingest_selected(
    session: Session,
    records: Sequence[dict[str, Any]],
    institution: Institution,
    settings: Settings,
) -> dict[str, int]:
    """Upsert только отобранных авторов — пул целиком в БД не кладём."""
    catalogue = {row.openalex_id: row.id for row in session.execute(select(Institution)).scalars()}
    n_candidates = 0
    for record in records:
        author = upsert_author(
            session, record, home_institution_id(record, catalogue, institution.id), settings
        )
        author.primary_field = primary_field(record)
        if author.is_supervisor_candidate:
            n_candidates += 1
    log.info(
        "authors_selected",
        institution=institution.openalex_id,
        total=len(records),
        candidates=n_candidates,
    )
    return {"total": len(records), "candidates": n_candidates}
