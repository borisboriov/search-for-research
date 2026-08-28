"""Supervisor-candidate heuristic (SPEC §3). Thresholds come from Settings, not code."""


def is_supervisor_candidate(
    *,
    works_count: int,
    h_index: int | None,
    last_publication_year: int | None,
    current_year: int,
    min_works: int,
    min_h_index: int,
    recent_years: int,
) -> bool:
    """works_count >= min_works AND a publication within the last ``recent_years``
    calendar years (inclusive of the current one) AND h_index >= min_h_index.

    Authors failing the heuristic are kept in the DB with the flag set to False.
    """
    if works_count < min_works:
        return False
    if h_index is None or h_index < min_h_index:
        return False
    if last_publication_year is None:
        return False
    return last_publication_year >= current_year - recent_years + 1
