"""Метрики выкладки (`scripts/sfr5c_deploy_metrics.py`): две разметки, три набора."""

import importlib.util
import sys
from pathlib import Path

import pytest

from sfr_match.evalset import Judgment, Query
from sfr_match.evaluate import QueryRun, Run

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.fixture(scope="module")
def dm():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "sfr5c_deploy_metrics", SCRIPTS / "sfr5c_deploy_metrics.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(ranking: dict[str, list[str]]) -> Run:
    return Run(
        variant="frida_clean",
        model_key="frida",
        hf_id=None,
        clean=True,
        k=10,
        index_version="frida_clean-9002p-test",
        results=[
            QueryRun(
                query_id=qid,
                latency_ms=1.0,
                hits=[
                    {"rank": i, "author_id": a, "name": a, "score": 0.5 - i / 100}
                    for i, a in enumerate(ids, start=1)
                ],
            )
            for qid, ids in ranking.items()
        ],
    )


def test_sets_split_the_relabelled_queries_out_of_the_22(dm) -> None:  # type: ignore[no-untyped-def]
    queries = [
        Query(id="q01", text="запрос один", expect="in-domain"),
        Query(id="q29", text="запрос два", expect="in-domain"),
        Query(id="q30", text="запрос три", expect="in-domain"),
        Query(id="q23", text="запрос край", expect="edge"),
    ]
    sets = dm.sets_of(queries)
    assert [q.id for q in sets["golden_in_domain_24"]] == ["q01", "q29", "q30"]
    assert [q.id for q in sets["golden_same_22"]] == ["q01"], "q29/q30 перемечены на ревью SFR-5"
    assert [q.id for q in sets["golden_edge"]] == ["q23"]


def test_unjudged_pairs_count_as_zero_and_are_reported(dm) -> None:  # type: ignore[no-untyped-def]
    """Слепая разметка обязана покрыть весь топ-5: пустые места видны отдельным числом."""
    run = _run({"q01": ["A1", "A2"], "q02": ["A3", "A4"]})
    queries = [
        Query(id="q01", text="запрос один", expect="in-domain"),
        Query(id="q02", text="запрос два", expect="in-domain"),
    ]
    judgments = {
        ("q01", "A1"): Judgment(query_id="q01", author_id="A1", grade=2),
        ("q01", "A2"): Judgment(query_id="q01", author_id="A2", grade=0),
    }
    summary = dm.summarize(run, queries, judgments)
    assert summary["n"] == 2
    assert summary["success_at_1"] == 0.5, "q02 без оценок — ноль, а не пропуск"
    assert summary["success_at_5"] == 0.5
    assert summary["unjudged_pairs"] == 2, "обе пары q02 не оценены"
    assert summary["per_query"][0]["grades"] == [2, 0]
