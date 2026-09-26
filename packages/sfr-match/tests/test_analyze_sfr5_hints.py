"""`threshold_hints` (`scripts/analyze_sfr5.py`): рецепт weak/high в коде, а не в прозе.

Рецепт разошёлся между отчётами (§5 SFR-5c посчитал `high` по всем in-domain,
SFR-5 и SFR-5b — по запросам с Success@1 = 1) именно потому, что жил только
текстом. Тест закрепляет тот, что дал боевые 0.47 и 0.49.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from sfr_match.evalset import Query
from sfr_match.evaluate import QueryRun, Run

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.fixture(scope="module")
def az():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("analyze_sfr5", SCRIPTS / "analyze_sfr5.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(scores: dict[str, float]) -> Run:
    return Run(
        variant="frida_clean",
        model_key="frida",
        hf_id=None,
        clean=True,
        k=10,
        index_version="v",
        results=[
            QueryRun(
                query_id=qid,
                latency_ms=1.0,
                hits=[{"rank": 1, "author_id": "A1", "name": "A1", "score": score}],
            )
            for qid, score in scores.items()
        ],
    )


def test_high_is_the_median_of_queries_whose_top1_is_relevant(az) -> None:  # type: ignore[no-untyped-def]
    run = _run({"q01": 0.3906, "q02": 0.50, "q03": 0.44, "q04": 0.62})
    queries = [Query(id=f"q0{i}", text=f"запрос {i}", expect="in-domain") for i in range(1, 5)]
    rows = [
        {"id": "q01", "s1": False, "s5": True, "top1": 0.3906},
        {"id": "q02", "s1": True, "s5": True, "top1": 0.50},
        {"id": "q03", "s1": False, "s5": True, "top1": 0.44},
        {"id": "q04", "s1": True, "s5": True, "top1": 0.62},
    ]
    hints = az.threshold_hints(run, queries, rows)
    assert hints["in_domain_min"] == 0.3906
    assert hints["weak"] == pytest.approx(0.40), "минимум in-domain, вверх по сетке 0.01"
    assert hints["lucky_n"] == 2, "«удачные» — только те, у кого top-1 релевантен"
    assert hints["lucky_median"] == pytest.approx(0.56)
    assert hints["high"] == pytest.approx(0.56), "медиана удачных, вниз по сетке"
    assert hints["all_in_domain_median"] == pytest.approx(0.47)
    assert hints["high_by_all_in_domain"] == pytest.approx(0.47), "рецепт §5 SFR-5c — для сравнения"


def test_edge_queries_do_not_move_the_hints(az) -> None:  # type: ignore[no-untyped-def]
    """Пороги выведены из in-domain: edge слабее по построению и медиану бы утянул."""
    run = _run({"q01": 0.50, "q23": 0.10})
    queries = [
        Query(id="q01", text="запрос один", expect="in-domain"),
        Query(id="q23", text="запрос край", expect="edge"),
    ]
    rows = [
        {"id": "q01", "s1": True, "s5": True, "top1": 0.50},
        {"id": "q23", "s1": True, "s5": True, "top1": 0.10},
    ]
    hints = az.threshold_hints(run, queries, rows)
    assert hints["in_domain_min"] == 0.50 and hints["lucky_n"] == 1
