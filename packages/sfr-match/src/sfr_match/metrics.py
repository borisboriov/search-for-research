"""Ranking metrics: Success@k, nDCG@k, MRR (SPEC_SFR1 §5).

All functions take a *ranked list of grades* (0/1/2 from the judgments) —
they know nothing about models, so they are trivially testable.
"""

from collections.abc import Sequence
from math import log2

RELEVANT_GRADE = 2  # "direct specialisation match" — the product-level bar


def success_at_k(grades: Sequence[int], k: int = 5, min_grade: int = RELEVANT_GRADE) -> bool:
    """True when at least one of the top-k results is graded ``>= min_grade``."""
    return any(grade >= min_grade for grade in grades[:k])


def dcg(grades: Sequence[int], k: int) -> float:
    """Discounted cumulative gain with linear gain (``gain = grade``)."""
    return sum(grade / log2(rank + 1) for rank, grade in enumerate(grades[:k], start=1))


def ndcg_at_k(grades: Sequence[int], all_grades: Sequence[int], k: int = 10) -> float:
    """nDCG@k against the ideal ranking of everything judged for this query.

    ``all_grades`` is the pool of grades known for the query (pooled evaluation):
    the ideal ranking puts the highest grades first.
    """
    ideal = dcg(sorted(all_grades, reverse=True), k)
    if ideal == 0:
        return 0.0
    return dcg(grades, k) / ideal


def reciprocal_rank(grades: Sequence[int], min_grade: int = RELEVANT_GRADE) -> float:
    """1/rank of the first result graded ``>= min_grade``; 0.0 when there is none."""
    for rank, grade in enumerate(grades, start=1):
        if grade >= min_grade:
            return 1.0 / rank
    return 0.0


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean; 0.0 for an empty sequence (keeps report tables total)."""
    return sum(values) / len(values) if values else 0.0
