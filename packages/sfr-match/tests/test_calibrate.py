"""Threshold calibration: pure arithmetic over top-1 scores (SPEC_SFR2 §4)."""

from sfr_match.calibrate import ThresholdRow, calibrate, grid, recommend, top1_scores
from sfr_match.evalset import Query
from sfr_match.evaluate import QueryRun, Run


def _run(scores: dict[str, float]) -> Run:
    return Run(
        variant="frida_clean",
        model_key="frida",
        hf_id="ai-forever/FRIDA",
        clean=True,
        k=10,
        results=[
            QueryRun(query_id=query_id, latency_ms=1.0, hits=[{"author_id": "A1", "score": score}])
            for query_id, score in scores.items()
        ],
    )


def test_top1_scores_are_filtered_by_query_kind() -> None:
    queries = [
        Query(id="q1", text="физика частиц", expect="in-domain"),
        Query(id="q2", text="право", expect="out-of-domain"),
    ]
    run = _run({"q1": 0.44, "q2": 0.31})
    assert top1_scores(run, queries, {"in-domain"}) == {"q1": 0.44}
    assert top1_scores(run, queries, {"out-of-domain"}) == {"q2": 0.31}


def test_a_query_without_hits_is_left_out() -> None:
    queries = [Query(id="q1", text="физика частиц", expect="in-domain")]
    run = Run(variant="v", model_key="m", hf_id=None, clean=False, k=10, results=[])
    assert top1_scores(run, queries, {"in-domain"}) == {}


def test_grid_spans_every_observed_score() -> None:
    values = grid({"a": 0.31}, {"b": 0.44})
    assert min(values) <= 0.31 and max(values) >= 0.44


def test_row_counts_wrong_cuts_and_caught_ood() -> None:
    rows = calibrate({"q1": 0.34, "q2": 0.50}, {"q3": 0.40}, {"q4": 0.30, "q5": 0.36}, [0.35])
    assert rows == [
        ThresholdRow(threshold=0.35, false_cuts_in_domain=1, false_cuts_edge=0, ood_caught=1)
    ]


def test_recommendation_never_cuts_a_real_query() -> None:
    rows = calibrate(
        {"q1": 0.34, "q2": 0.50},
        {},
        {"q4": 0.30, "q5": 0.33},
        [0.30, 0.31, 0.34, 0.40],
    )
    best = recommend(rows)
    assert best is not None
    assert best.threshold == 0.34  # 0.40 would wrongly cut q1
    assert best.ood_caught == 2


def test_recommendation_sits_in_the_middle_of_the_safe_plateau() -> None:
    """Separated distributions leave a whole interval; the edge of it is fragile."""
    rows = calibrate({"q1": 0.50}, {}, {"o1": 0.20}, [0.21, 0.25, 0.30, 0.35, 0.40, 0.45, 0.55])
    best = recommend(rows)
    assert best is not None
    assert best.ood_caught == 1
    assert best.threshold == 0.35  # middle of 0.21..0.45, not 0.45


def test_edge_queries_are_spared_when_that_costs_no_coverage() -> None:
    rows = calibrate({"q1": 0.50}, {"q2": 0.30}, {"o1": 0.20}, [0.25, 0.28, 0.35])
    best = recommend(rows)
    assert best is not None
    assert best.false_cuts_edge == 0
    assert best.ood_caught == 1


def test_no_recommendation_when_every_threshold_cuts_something() -> None:
    rows = calibrate({"q1": 0.10}, {}, {"q2": 0.50}, [0.20, 0.30])
    assert recommend(rows) is None
