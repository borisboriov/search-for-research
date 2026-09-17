"""Метрики решения SFR-5b (`scripts/sfr5b_decision_metrics.py`): логика на синтетике.

Скрипт лежит вне пакетов, поэтому грузится по пути от корня репозитория.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from sfr_match.evalset import Judgment, Query
from sfr_match.evaluate import QueryRun, Run

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "sfr5b_decision_metrics.py"


@pytest.fixture(scope="module")
def dm():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("sfr5b_decision_metrics", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses резолвят аннотации через sys.modules — модуль надо зарегистрировать.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(version: str, ranking: dict[str, list[tuple[str, float]]]) -> Run:
    results = [
        QueryRun(
            query_id=qid,
            latency_ms=1.0,
            hits=[
                {"rank": i, "author_id": a, "name": a, "score": s}
                for i, (a, s) in enumerate(hits, start=1)
            ],
        )
        for qid, hits in ranking.items()
    ]
    return Run(
        variant="frida_clean",
        model_key="frida",
        hf_id=None,
        clean=True,
        k=10,
        index_version=version,
        results=results,
    )


def _judgment(qid: str, aid: str, grade: int) -> tuple[tuple[str, str], Judgment]:
    return (qid, aid), Judgment(query_id=qid, author_id=aid, grade=grade)


def test_coverage_displacement_and_aliases(dm) -> None:  # type: ignore[no-untyped-def]
    golden = [
        Query(id="q01", text="запрос один", expect="in-domain"),
        Query(id="q29", text="перемеченный", expect="in-domain"),
        Query(id="q40", text="edge", expect="edge"),
    ]
    ood = [Query(id="o01", text="посторонний", expect="out-of-domain")]
    old = dm.Catalogue({"OLD1": "МФТИ", "OLD2": "МГУ", "OLD3": "МФТИ", "DUP": "МГУ"})
    new = dm.Catalogue(
        {"OLD1": "МФТИ", "OLD2": "МГУ", "OLD3": "МФТИ", "NEW1": "ВШЭ", "NEW2": "ИТМО"}
    )
    # DUP (старый каталог) склеен в NEW2 нового: NEW2 — тот же человек, а не новый.
    aliases = dm.Aliases({"DUP": "NEW2"})

    before = _run(
        "old",
        {
            "q01": [("OLD1", 0.50), ("OLD2", 0.45), ("OLD3", 0.40)],
            "q29": [("OLD2", 0.44), ("DUP", 0.30)],
            "q40": [("OLD3", 0.35)],
        },
    )
    after = _run(
        "new",
        {
            # NEW1 (grade 2) встал первым, OLD2 (grade 2) вылетел из топ-5 — но тут
            # топ-5 не заполнен, поэтому OLD2 просто отсутствует; OLD3 (grade 0) остался.
            "q01": [("NEW1", 0.55), ("OLD1", 0.50), ("OLD3", 0.40)],
            # NEW2 = DUP по склейке: оценка берётся с DUP (2), «новым» не считается.
            "q29": [("NEW2", 0.46), ("OLD2", 0.44)],
            "q40": [("OLD3", 0.36)],
        },
    )
    ood_before = _run("old", {"o01": [("OLD1", 0.20)]})
    ood_after = _run("new", {"o01": [("NEW1", 0.25)]})
    judgments = dict(
        [
            _judgment("q01", "OLD1", 2),
            _judgment("q01", "OLD2", 2),
            _judgment("q01", "OLD3", 0),
            _judgment("q01", "NEW1", 2),
            _judgment("q29", "DUP", 2),
            _judgment("q29", "OLD2", 1),
            _judgment("q40", "OLD3", 2),
        ]
    )

    payload = dm.decision_metrics(
        golden=golden,
        external=[],
        ood=ood,
        before=before,
        after=after,
        ood_before=ood_before,
        ood_after=ood_after,
        ext_before=None,
        ext_after=None,
        judgments=judgments,
        old=old,
        new=new,
        aliases=aliases,
    )

    g24 = payload["sets"]["golden_in_domain_24"]
    assert g24["n_queries"] == 2
    # q01: новый NEW1 с оценкой 2 встал первым; q29: NEW2 — склейка, не новый.
    assert g24["coverage_gain"] == {
        "queries_with_new_in_top5": 0.5,
        "queries_with_new_grade2_in_top5": 0.5,
        "queries_top1_new": 0.5,
    }
    # q01: OLD2 (grade 2) вылетел, его место занял новый grade 2.
    assert g24["displacement"]["old_grade2_left_top5"] == 1
    assert g24["displacement"]["entrants_new_grade2"] == 1
    assert g24["displacement"]["entrants_new_grade_le1"] == 0
    # q29: NEW2 и DUP — один человек, топ-5 по каноническим id не изменился:
    # ни входов, ни вытеснений.
    assert g24["displacement"]["entrants_old"] == 0
    assert payload["per_query"]["golden"][1]["entrants"] == {}
    # q29: было top-1 OLD2 (grade 1) — промах; стало NEW2 с оценкой 2, найденной
    # через склеенный DUP, — попадание.
    assert g24["success_at_1"] == {"before": 0.5, "after": 1.0}
    assert payload["judgments_via_alias"] >= 1
    assert g24["unjudged_pairs_in_top5_after"] == 0

    # Набор «те же 22» исключает q29.
    assert payload["sets"]["golden_same_22"]["n_queries"] == 1
    assert payload["sets"]["golden_edge"]["n_queries"] == 1
    assert payload["sets"]["external"]["n_queries"] == 0

    inst = payload["institutions"]
    assert inst["before"]["distinct_in_top10_union"] == 2  # МФТИ, МГУ
    assert inst["after"]["distinct_in_top10_union"] == 4  # + ВШЭ, ИТМО

    shift = payload["scale_shift"]
    assert shift["ood_median_top1"] == {"before": 0.2, "after": 0.25}
    assert shift["golden_in_domain_median_top1"]["after"] == pytest.approx(0.505)

    table = dm.render_table(payload)
    assert "golden_in_domain_24" in table and "external" not in table.split("\n")[2]


def test_top_dedups_by_alias(dm) -> None:  # type: ignore[no-untyped-def]
    run = _run("x", {"q": [("A", 0.5), ("B", 0.4), ("C", 0.3)]})
    aliases = dm.Aliases({"B": "A"})
    assert dm._top(run, "q", 5, aliases) == ["A", "C"]
    assert dm.Aliases().group("Z") == {"Z"}
    assert aliases.group("B") == {"A", "B"}
