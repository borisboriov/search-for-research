"""Ranking metrics on a hand-checked synthetic fixture."""

import pytest

from sfr_match.metrics import dcg, mean, ndcg_at_k, reciprocal_rank, success_at_k

# One query: the ranking returned grades [2, 0, 1]; the judged pool holds [2, 1, 1, 0].
RANKED = [2, 0, 1]
POOL = [2, 1, 1, 0]


def test_success_at_5_strict() -> None:
    assert success_at_k([0, 0, 2, 0, 0], k=5, min_grade=2)
    assert not success_at_k([0, 0, 1, 1, 0], k=5, min_grade=2)


def test_success_at_5_soft_accepts_grade_1() -> None:
    assert success_at_k([0, 0, 1, 1, 0], k=5, min_grade=1)


def test_success_at_k_ignores_results_below_the_cutoff() -> None:
    assert not success_at_k([0, 0, 0, 0, 0, 2], k=5, min_grade=2)


def test_dcg_matches_manual_computation() -> None:
    # 2/log2(2) + 0/log2(3) + 1/log2(4) = 2 + 0 + 0.5
    assert dcg(RANKED, k=3) == pytest.approx(2.5)


def test_ndcg_matches_manual_computation() -> None:
    # IDCG@3 over [2, 1, 1] = 2/1 + 1/log2(3) + 1/log2(4) = 2 + 0.6309298 + 0.5
    assert ndcg_at_k(RANKED, POOL, k=3) == pytest.approx(2.5 / 3.1309298, rel=1e-6)


def test_ndcg_is_zero_when_nothing_relevant_was_judged() -> None:
    assert ndcg_at_k([0, 0], [0, 0, 0], k=2) == 0.0


def test_perfect_ranking_scores_one() -> None:
    assert ndcg_at_k([2, 1, 1, 0], [2, 1, 1, 0], k=4) == pytest.approx(1.0)


def test_reciprocal_rank_uses_the_first_relevant_hit() -> None:
    assert reciprocal_rank([0, 1, 2, 2]) == pytest.approx(1 / 3)
    assert reciprocal_rank([2, 0, 0]) == 1.0
    assert reciprocal_rank([0, 1, 1]) == 0.0


def test_mean_of_empty_is_zero() -> None:
    assert mean([]) == 0.0
    assert mean([1.0, 0.0]) == 0.5
