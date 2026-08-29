"""Rendering of docs/SFR2_REPORT.md from measured artefacts."""

from sfr_match.calibrate import calibrate, recommend
from sfr_match.evalset import Query
from sfr_match.report import VariantMetrics
from sfr_match.report2 import (
    render_calibration,
    render_composition,
    render_examples,
    render_faiss_check,
    render_resources,
    render_sfr2_report,
)

RESOURCES = {
    "measured_at": "2026-08-29 21:00:00",
    "host": {
        "platform": "macOS-15",
        "machine": "arm64",
        "docker": True,
        "docker_info": "8G 8 aarch64",
    },
    "models": [
        {
            "model": "frida",
            "cold_start_s": 42.0,
            "rss_idle_mb": 3300.0,
            "rss_load_mb": 3800.0,
            "seq_p50_ms": 210.0,
            "seq_p95_ms": 260.0,
            "conc4_p50_ms": 700.0,
            "conc4_p95_ms": 900.0,
            "conc4_rps": 5.1,
            "image_mb": 2365.0,
            "faiss_vs_numpy": {
                "backend_checked": "numpy",
                "queries": 8,
                "identical_order": True,
                "mismatched_queries": [],
                "max_score_delta": 1e-7,
            },
        }
    ],
    "examples": [
        {
            "request": {"query": "нейросети", "k": 2},
            "took_ms": 180.0,
            "below_threshold": False,
            "results": [
                {
                    "rank": 1,
                    "name": "V. Knyaz",
                    "score": 0.456,
                    "institution": "МФТИ",
                    "h_index": 18,
                    "topics": ["Imaging"],
                }
            ],
        }
    ],
}


def _metrics(variant: str, success1: float) -> VariantMetrics:
    return VariantMetrics(
        variant=variant,
        model_key="frida",
        clean=True,
        n_profiles=535,
        n_in_domain=22,
        success1_strict=success1,
        success3_strict=1.0,
        success5_strict=1.0,
        success5_soft=1.0,
        ndcg10=0.66,
        mrr=0.9,
        build_seconds=623.9,
        latency_ms_mean=136.0,
        latency_ms_median=123.0,
        params_m=823.0,
        judged_share=1.0,
        ood_top1_mean=0.3,
        ood_false_positives=0,
        in_domain_top1_min=0.34,
        in_domain_top1_mean=0.44,
        ood_top1_max=0.33,
    )


def test_resources_table_says_where_it_was_measured() -> None:
    text = "\n".join(render_resources(RESOURCES))
    assert "в контейнере" in text and "arm64" in text
    assert "| `frida` | 42.0 | 3300.0 |" in text


def test_resources_section_admits_when_nothing_was_measured() -> None:
    assert "Замер не выполнялся" in "\n".join(render_resources({}))


def test_faiss_check_reports_the_backend_and_the_score_delta() -> None:
    text = "\n".join(render_faiss_check(RESOURCES))
    assert "FAISS ≡ NumPy" in text and "да" in text


def test_faiss_check_is_skipped_when_there_was_no_check() -> None:
    assert render_faiss_check({"models": [{"model": "frida"}]}) == []


def test_calibration_table_collapses_thresholds_that_change_nothing() -> None:
    rows = calibrate({"q1": 0.40}, {}, {"o1": 0.30}, [0.20, 0.21, 0.22, 0.35, 0.45])
    text = "\n".join(
        render_calibration(
            rows, recommend(rows), {"in_domain": 1, "edge": 0, "ood": 1}, "frida_clean", 0.35
        )
    )
    assert "| 0.20 |" in text and "| 0.21 |" not in text  # identical rows are dropped
    assert "**←**" in text  # the recommendation is marked
    assert "Было в SFR-1: 0.35" in text


def test_calibration_says_so_when_no_threshold_is_safe() -> None:
    rows = calibrate({"q1": 0.10}, {}, {"o1": 0.50}, [0.20])
    text = "\n".join(
        render_calibration(rows, recommend(rows), {"in_domain": 1, "edge": 0, "ood": 1}, "v", 0.35)
    )
    assert "Безопасного порога нет" in text


def test_composition_table_names_the_composition_and_shows_success_at_1() -> None:
    text = "\n".join(
        render_composition(
            [_metrics("frida_clean", 0.77), _metrics("frida_clean__topics", 0.68)],
            {"frida_clean": 1100.0, "frida_clean__topics": 210.0},
            {"frida_clean": "frida_clean-535p-abe35971"},
        )
    )
    assert "полный profile_text (бейзлайн)" in text and "только темы" in text
    assert "**77%**" in text and "**68%**" in text
    assert "frida_clean-535p-abe35971" in text


def test_examples_render_as_a_ranked_block() -> None:
    text = "\n".join(render_examples(RESOURCES))
    assert "below_threshold: false" in text and "V. Knyaz" in text


def test_full_report_carries_the_hand_written_notes_through() -> None:
    rows = calibrate({"q1": 0.40}, {}, {"o1": 0.30}, [0.35])
    text = render_sfr2_report(
        composition=[_metrics("frida_clean", 0.77)],
        chars={"frida_clean": 1100.0},
        index_versions={"frida_clean": "frida_clean-535p-abe35971"},
        calibration=rows,
        recommended=recommend(rows),
        calibration_counts={"in_domain": 1, "edge": 0, "ood": 1},
        calibration_variant="frida_clean",
        previous_threshold=0.35,
        resources=RESOURCES,
        queries=[Query(id="q1", text="физика частиц", expect="in-domain")],
        ood_queries=[Query(id="o1", text="ремонт стиральной машины", expect="out-of-domain")],
        n_profiles=535,
        notes="## Разбор\n\nручной текст",
    )
    assert "# SFR-2" in text and "535 профилей" in text
    assert "ручной текст" in text.split("## Разбор")[-1]
