from sfr_core.heuristics import is_supervisor_candidate

THRESHOLDS = {
    "current_year": 2026,
    "min_works": 10,
    "min_h_index": 5,
    "recent_years": 3,
}


def check(works_count: int, h_index: int | None, last_year: int | None) -> bool:
    return is_supervisor_candidate(
        works_count=works_count,
        h_index=h_index,
        last_publication_year=last_year,
        **THRESHOLDS,  # type: ignore[arg-type]
    )


def test_passes_all_thresholds() -> None:
    assert check(10, 5, 2026) is True


def test_boundary_recent_year_inclusive() -> None:
    # recent_years=3 with current_year=2026 → 2024, 2025, 2026 count as recent
    assert check(10, 5, 2024) is True
    assert check(10, 5, 2023) is False


def test_works_count_boundary() -> None:
    assert check(9, 5, 2026) is False
    assert check(10, 5, 2026) is True


def test_h_index_boundary() -> None:
    assert check(10, 4, 2026) is False
    assert check(10, 5, 2026) is True


def test_missing_h_index_fails() -> None:
    assert check(100, None, 2026) is False


def test_missing_last_publication_fails() -> None:
    assert check(100, 50, None) is False
