"""Metric aggregation and report rendering on a synthetic run."""

from pathlib import Path

from sfr_match.evalset import Judgment, Query
from sfr_match.evaluate import QueryRun, Run
from sfr_match.report import compute_metrics, read_notes, render_report, sample_for_review

QUERIES = [
    Query(id="q1", text="сверхпроводимость", expect="in-domain"),
    Query(id="q2", text="нейросети для текстов", expect="in-domain"),
    Query(id="q3", text="выпечка хлеба", expect="out-of-domain"),
]
JUDGMENTS = {
    ("q1", "A1"): Judgment(query_id="q1", author_id="A1", grade=2, rationale="прямое совпадение"),
    ("q1", "A2"): Judgment(query_id="q1", author_id="A2", grade=1, rationale="смежное"),
    ("q2", "A3"): Judgment(query_id="q2", author_id="A3", grade=1, rationale="смежное"),
    ("q3", "A2"): Judgment(query_id="q3", author_id="A2", grade=0, rationale="нерелевантно"),
}


def _run(variant: str = "e5-base", clean: bool = False) -> Run:
    def hits(pairs: list[tuple[str, float]]) -> list[dict[str, object]]:
        return [
            {"rank": rank, "author_id": author_id, "name": author_id, "score": score}
            for rank, (author_id, score) in enumerate(pairs, start=1)
        ]

    return Run(
        variant=variant,
        model_key="e5-base",
        hf_id="intfloat/multilingual-e5-base",
        clean=clean,
        k=10,
        n_profiles=3,
        build_seconds=1.5,
        results=[
            QueryRun(query_id="q1", latency_ms=12.0, hits=hits([("A1", 0.9), ("A2", 0.8)])),
            QueryRun(query_id="q2", latency_ms=8.0, hits=hits([("A3", 0.7), ("A1", 0.6)])),
            QueryRun(query_id="q3", latency_ms=10.0, hits=hits([("A2", 0.4)])),
        ],
    )


def test_success_at_5_counts_only_in_domain_queries() -> None:
    metrics = compute_metrics(_run(), QUERIES, JUDGMENTS)
    assert metrics.n_in_domain == 2
    assert metrics.success5_strict == 0.5  # q1 has a grade-2 hit, q2 does not
    assert metrics.success5_soft == 1.0  # both have a grade>=1 hit


def test_out_of_domain_scores_are_tracked_separately() -> None:
    metrics = compute_metrics(_run(), QUERIES, JUDGMENTS)
    assert metrics.ood_top1_mean == 0.4
    assert metrics.ood_top1_max == 0.4
    assert metrics.ood_false_positives == 0
    assert metrics.in_domain_top1_min == 0.7


def test_unjudged_hits_count_as_non_relevant() -> None:
    run = _run()
    run.results[0].hits.append({"rank": 3, "author_id": "A9", "name": "A9", "score": 0.5})
    metrics = compute_metrics(run, QUERIES, JUDGMENTS)
    assert metrics.judged_share < 1.0


def test_latency_and_model_size_are_carried_into_the_table() -> None:
    metrics = compute_metrics(_run(), QUERIES, JUDGMENTS)
    assert metrics.latency_ms_mean == 10.0
    assert metrics.params_m == 278.0
    assert metrics.build_seconds == 1.5


def test_render_report_lists_variants_best_first() -> None:
    good = compute_metrics(_run("e5-base"), QUERIES, JUDGMENTS)
    bad = compute_metrics(_run("minilm"), QUERIES, {})
    text = render_report([bad, good], QUERIES, JUDGMENTS)
    assert text.index("`e5-base`") < text.index("`minilm`")
    assert "Success@5" in text
    assert "30" not in text.split("## Сводная таблица")[0].split("Golden set")[0]


def test_render_report_appends_handwritten_notes() -> None:
    metrics = [compute_metrics(_run(), QUERIES, JUDGMENTS)]
    text = render_report(metrics, QUERIES, JUDGMENTS, notes="## Рекомендация\n\nБерём e5.")
    assert text.rstrip().endswith("Берём e5.")


def test_read_notes_returns_empty_string_when_absent(tmp_path: Path) -> None:
    assert read_notes(tmp_path / "nope.md") == ""


def test_review_sample_is_deterministic_and_human_readable() -> None:
    pool = sorted(JUDGMENTS)
    profiles = {
        "A1": {"name": "Первый", "topics": ["Superconductivity"]},
        "A2": {"name": "Второй", "topics": ["Magnetism"]},
        "A3": {"name": "Третий", "topics": ["NLP"]},
    }
    first = sample_for_review(pool, QUERIES, JUDGMENTS, profiles, n=3)
    second = sample_for_review(pool, QUERIES, JUDGMENTS, profiles, n=3)
    assert first == second
    assert first.count("## ") == 3
    assert "прямое совпадение" in first or "смежное" in first
