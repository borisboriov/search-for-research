"""Стратифицированный отбор авторов (SPEC_SFR5 §2)."""

from typing import Any

from sfr_core.settings import Settings
from sfr_etl.catalog import (
    FIELD_UNKNOWN,
    allocate_quota,
    home_institution_id,
    passes_heuristic,
    primary_field,
    stratified_select,
)

SETTINGS = Settings(
    _env_file=None,  # type: ignore[call-arg]
    openalex_mailto="test@example.com",
    supervisor_min_works=10,
    supervisor_min_h_index=5,
    supervisor_recent_years=3,
)


def author(
    short_id: str,
    *,
    field: str | None = "Physics and Astronomy",
    h_index: int = 10,
    works_count: int = 50,
    last_year: int = 2026,
    name: str | None = None,
) -> dict[str, Any]:
    topics = (
        []
        if field is None
        else [{"display_name": f"{field} topic", "count": 7, "field": {"display_name": field}}]
    )
    return {
        "id": f"https://openalex.org/{short_id}",
        "display_name": name or short_id,
        "works_count": works_count,
        "summary_stats": {"h_index": h_index},
        "counts_by_year": [{"year": last_year, "works_count": 3}],
        "topics": topics,
    }


def test_primary_field_takes_the_heaviest_field() -> None:
    record = {
        "topics": [
            {"display_name": "a", "count": 2, "field": {"display_name": "Computer Science"}},
            {"display_name": "b", "count": 9, "field": {"display_name": "Economics"}},
            {"display_name": "c", "count": 1, "field": {"display_name": "Computer Science"}},
        ]
    }
    assert primary_field(record) == "Economics"


def test_primary_field_without_topics() -> None:
    assert primary_field({"topics": []}) == FIELD_UNKNOWN


def test_recency_is_applied_locally() -> None:
    # Серверный фильтр OpenAlex умеет только works_count и h-index; свежесть — здесь.
    fresh = author("A1", last_year=2026)
    stale = author("A2", last_year=2015)
    assert passes_heuristic(fresh, SETTINGS, current_year=2026)
    assert not passes_heuristic(stale, SETTINGS, current_year=2026)


def test_allocate_quota_gives_small_fields_a_floor() -> None:
    sizes = {"Physics": 900, "Computer Science": 40, "Arts": 5}
    allocation = allocate_quota(sizes, quota=100, floor=8)
    assert sum(allocation.values()) == 100
    assert allocation["Arts"] == 5  # пол ограничен размером области
    assert allocation["Computer Science"] >= 8
    assert allocation["Physics"] > allocation["Computer Science"]


def test_allocate_quota_returns_everything_when_pool_is_small() -> None:
    sizes = {"Physics": 3, "Economics": 2}
    assert allocate_quota(sizes, quota=100) == sizes


def test_allocate_quota_when_floors_exceed_quota() -> None:
    sizes = {f"F{i}": 50 for i in range(10)}
    allocation = allocate_quota(sizes, quota=20, floor=8)
    assert sum(allocation.values()) == 20
    assert max(allocation.values()) - min(allocation.values()) <= 1


def test_stratified_select_does_not_let_one_field_eat_the_quota() -> None:
    pool = [author(f"A{i}", field="Physics and Astronomy", h_index=50) for i in range(100)]
    pool += [author(f"B{i}", field="Computer Science", h_index=9) for i in range(20)]
    pool += [author(f"C{i}", field="Economics", h_index=8) for i in range(10)]
    selected, sizes = stratified_select(pool, quota=30, settings=SETTINGS, current_year=2026)
    fields = {primary_field(r) for r in selected}
    assert len(selected) == 30
    assert sizes == {"Physics and Astronomy": 100, "Computer Science": 20, "Economics": 10}
    # Без стратификации все 30 мест забрали бы физики с h-index 50.
    assert fields == {"Physics and Astronomy", "Computer Science", "Economics"}


def test_stratified_select_keeps_forced_ids() -> None:
    pool = [author(f"A{i}", field="Physics and Astronomy", h_index=100 - i) for i in range(50)]
    kept = "A49"  # самый слабый по h-index — без keep_ids не прошёл бы
    selected, _ = stratified_select(
        pool, quota=5, settings=SETTINGS, current_year=2026, keep_ids=[kept]
    )
    assert kept in {r["id"].rsplit("/", 1)[-1] for r in selected}


def test_stratified_select_drops_authors_failing_the_heuristic() -> None:
    pool = [author("A1"), author("A2", h_index=1), author("A3", last_year=2010)]
    selected, sizes = stratified_select(pool, quota=10, settings=SETTINGS, current_year=2026)
    assert [r["id"].rsplit("/", 1)[-1] for r in selected] == ["A1"]
    assert sum(sizes.values()) == 1


def test_home_institution_is_the_first_catalogue_affiliation() -> None:
    record = {
        "last_known_institutions": [
            {"id": "https://openalex.org/I999"},  # не в каталоге
            {"id": "https://openalex.org/I222"},
            {"id": "https://openalex.org/I111"},
        ]
    }
    catalogue = {"I111": 1, "I222": 2}
    # Не «тот вуз, чей ингест шёл последним», а первый из списка автора.
    assert home_institution_id(record, catalogue, fallback_db_id=1) == 2
    assert home_institution_id({}, catalogue, fallback_db_id=7) == 7
