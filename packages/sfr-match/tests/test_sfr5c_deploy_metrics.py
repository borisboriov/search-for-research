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


def test_merge_makes_the_old_grade_stale_and_the_pair_unjudged(dm) -> None:  # type: ignore[no-untyped-def]
    """#123, сценарий q17: оценку ставили профилю до склейки, после склейки у того
    же id другой profile_text — старая оценка не берётся, пара неоценённая."""
    from sfr_match.evalset import profile_fingerprint

    before, after = "Belogurov: LHCb", "Belogurov: LHCb + GERDA 0νββ"
    run = _run({"q17": ["A5107886204"]})
    queries = [Query(id="q17", text="нейтрино", expect="in-domain")]
    judged = {
        ("q17", "A5107886204"): Judgment(
            query_id="q17", author_id="A5107886204", grade=1, profile_fp=profile_fingerprint(before)
        )
    }
    current = {"A5107886204": profile_fingerprint(after)}
    usable, block = dm.drop_stale("слепая", judged, current)
    assert usable == {}
    assert block is not None and block["stale"] == 1
    assert block["stale_pairs"] == [["q17", "A5107886204"]]
    summary = dm.summarize(run, queries, usable)
    assert summary["unjudged_pairs"] == 1, "устаревшая оценка — неоценённая пара, а не 1"
    # Профиль не менялся — оценка остаётся; строк без отпечатка сверка не касается.
    same = {"A5107886204": profile_fingerprint(before)}
    assert dm.drop_stale("слепая", judged, same)[0] == judged
    legacy = {k: v.model_copy(update={"profile_fp": ""}) for k, v in judged.items()}
    usable, block = dm.drop_stale("накопленная", legacy, current)
    assert usable == legacy and block is None, "без отпечатка — как до #123, JSON без блока"


BORDERLINE_MD = """\
# Пары, где судья колебался

| Запрос | НР | Оценка | Альтернатива | В чём сомнение |
|---|---|---|---|---|
| `q01` | `A1` Имя — Вуз | **1** | 2 | формат выкладки: id первым, оценка жирным |
| `q02` | Имя (`A2`) | 2 | 1 | формат базы: id в скобках после имени |
| `q03` | `A3` Имя | 1 | — | без альтернативы строка не берётся |

Текст после таблицы: | `q09` | не строка таблицы |
"""


def test_borderline_table_is_read_in_both_formats(dm, tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "judgments_borderline_test.md"
    path.write_text(BORDERLINE_MD, encoding="utf-8")
    assert dm.load_borderline(path) == {("q01", "A1"): 2, ("q02", "A2"): 1}


def test_borderline_interval_moves_every_disputed_pair_down_then_up(dm) -> None:  # type: ignore[no-untyped-def]
    queries = [
        Query(id="q01", text="первый", expect="in-domain"),
        Query(id="q02", text="второй", expect="in-domain"),
    ]
    run = _run({"q01": ["A1", "A9"], "q02": ["A7", "A2"]})
    judgments = {
        ("q01", "A1"): Judgment(query_id="q01", author_id="A1", grade=1),
        ("q01", "A9"): Judgment(query_id="q01", author_id="A9", grade=0),
        ("q02", "A7"): Judgment(query_id="q02", author_id="A7", grade=0),
        ("q02", "A2"): Judgment(query_id="q02", author_id="A2", grade=2),
    }
    # Спорные: q01/A1 (1 или 2) и q02/A2 (2 или 1); пара вне разметки игнорируется.
    alternatives = {("q01", "A1"): 2, ("q02", "A2"): 1, ("q05", "A5"): 2}
    interval = dm.borderline_interval(run, queries, judgments, alternatives)
    assert interval["borderline_pairs"] == 3
    s1 = interval["golden_in_domain_24"]["success_at_1"]
    s5 = interval["golden_in_domain_24"]["success_at_5"]
    assert (s1["low"], s1["point"], s1["high"]) == (0.0, 0.0, 0.5), "вверх: q01/A1 → 2"
    assert (s5["low"], s5["point"], s5["high"]) == (0.0, 0.5, 1.0), "вниз: q02/A2 → 1"
    assert judgments[("q01", "A1")].grade == 1, "исходная разметка не меняется"
