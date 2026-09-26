"""Решающие пары (`scripts/sfr5c_decisive_pairs.py`): отбор запросов и слепой пул."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from sfr_match.evalset import Judgment, Query
from sfr_match.evaluate import QueryRun, Run

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.fixture(scope="module")
def dp():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "sfr5c_decisive_pairs", SCRIPTS / "sfr5c_decisive_pairs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(ranking: dict[str, list[tuple[str, float]]]) -> Run:
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
                hits=[
                    {"rank": i, "author_id": a, "name": a, "score": s}
                    for i, (a, s) in enumerate(hits, start=1)
                ],
            )
            for qid, hits in ranking.items()
        ],
    )


def _profiles(*ids: str) -> dict[str, dict[str, object]]:
    return {
        i: {
            "id": i,
            "name": f"Имя {i}",
            "institution": "МФТИ",
            "topics": ["тема"],
            "profile_text": f"{i} — МФТИ. Работы: «Статья {i}» (2024).",
        }
        for i in ids
    }


@pytest.fixture
def scene(dp):  # type: ignore[no-untyped-def]
    queries = [
        Query(id="q01", text="меняется топ-1", expect="in-domain"),
        Query(id="q02", text="ничего не меняется", expect="in-domain"),
        Query(id="q03", text="расходятся только две точки из трёх", expect="edge"),
    ]
    base = dp.PointRuns(
        name="база",
        run=_run(
            {
                "q01": [("A1", 0.5), ("A2", 0.4)],
                "q02": [("A1", 0.5)],
                "q03": [("A1", 0.5), ("A2", 0.4)],
            }
        ),
        profiles=_profiles("A1", "A2"),
    )
    cap = dp.PointRuns(
        name="потолок",
        run=_run(
            {
                "q01": [("B1", 0.6), ("A1", 0.5)],
                "q02": [("A1", 0.5)],
                "q03": [("A1", 0.5), ("A2", 0.4)],
            }
        ),
        profiles=_profiles("A1", "A2", "B1"),
    )
    full = dp.PointRuns(
        name="полный",
        run=_run(
            {
                "q01": [("B1", 0.6), ("A1", 0.5)],
                "q02": [("A1", 0.5)],
                "q03": [("C9", 0.7), ("A1", 0.5)],
            }
        ),
        profiles=_profiles("A1", "A2", "B1", "C9"),
    )
    judgments = {
        ("q01", "A1"): Judgment(query_id="q01", author_id="A1", grade=2),
        ("q01", "B1"): Judgment(query_id="q01", author_id="B1", grade=2),
        ("q02", "A1"): Judgment(query_id="q02", author_id="A1", grade=2),
        ("q03", "A1"): Judgment(query_id="q03", author_id="A1", grade=2),
        ("q03", "C9"): Judgment(query_id="q03", author_id="C9", grade=0),
    }
    return queries, [base, cap, full], judgments


def test_decisive_queries_catch_any_pairwise_difference(dp, scene) -> None:  # type: ignore[no-untyped-def]
    queries, points, judgments = scene
    rows = dp.decisive_queries(queries, points, judgments)
    ids = [row["query"].id for row in rows]
    # q01 — сменился топ-1; q03 — разошлись только полный каталог и две левые точки.
    assert ids == ["q01", "q03"], "q02 одинаков во всех трёх точках — не решающий"
    assert dp_changed(rows, "q01") == ["top1"], "S@1 и S@5 держатся, меняется личность топ-1"
    assert "s1" in dp_changed(rows, "q03")


def dp_changed(rows: list[dict[str, object]], query_id: str) -> list[str]:
    return next(row["changed"] for row in rows if row["query"].id == query_id)  # type: ignore[union-attr,index]


def test_rejudge_pool_is_blind_and_deduplicated(dp, scene) -> None:  # type: ignore[no-untyped-def]
    queries, points, judgments = scene
    rows = dp.decisive_queries(queries, points, judgments)
    pool = dp.rejudge_pool(rows, points)
    keys = [(r["query_id"], r["author_id"]) for r in pool]
    assert len(keys) == len(set(keys)), "пара встречается один раз, а не по разу на точку"
    assert keys == sorted(keys, key=lambda k: (k[1], k[0])), "сортировка по author_id"
    # q01 → {A1, A2, B1}, q03 → {A1, A2, C9}: топ-5 всех трёх точек, объединение.
    assert keys == [
        ("q01", "A1"),
        ("q03", "A1"),
        ("q01", "A2"),
        ("q03", "A2"),
        ("q01", "B1"),
        ("q03", "C9"),
    ]
    fields = set(pool[0])
    assert fields == {
        "query_id",
        "author_id",
        "query",
        "expect",
        "name",
        "topics",
        "profile_text",
    }, "ни точки, ни прежней оценки в пуле быть не должно"
    assert all("profile_text" in json.dumps(r, ensure_ascii=False) for r in pool)


def test_decisive_section_shows_three_points_and_works(dp, scene) -> None:  # type: ignore[no-untyped-def]
    queries, points, judgments = scene
    rows = dp.decisive_queries(queries, points, judgments)
    text = dp.render_decisive_section(rows, points, judgments)
    assert "решающ" in text.lower() and "**2**" in text
    assert "| база |" in text and "| потолок |" in text and "| полный |" in text
    assert "«Статья B1» (2024)" in text, "названия работ обязательны (#107)"
    assert "`q02`" not in text


def test_decisive_section_shows_both_judges(dp, scene) -> None:  # type: ignore[no-untyped-def]
    """Расхождение двух судей на решающей паре видно в самой выборке, а не в другом файле."""
    queries, points, judgments = scene
    rows = dp.decisive_queries(queries, points, judgments)
    rejudged = [
        dp.Rejudge(
            label="v1",
            grades={
                ("q01", "B1"): Judgment(query_id="q01", author_id="B1", grade=1, judge="fable"),
                ("q01", "A1"): Judgment(query_id="q01", author_id="A1", grade=2, judge="fable"),
            },
        )
    ]
    text = dp.render_decisive_section(rows, points, judgments, rejudged)
    assert "расхождений с накопленной 1" in text
    assert "2 → 1 ⚠" in text, "расхождение помечено"
    assert "2 = 2" in text, "совпадение показано как совпадение"


def test_decisive_section_shows_every_rejudge_pass(dp, scene) -> None:  # type: ignore[no-untyped-def]
    """Два пересуда — три колонки «было → v1 → v2» в одной строке (#114)."""
    queries, points, judgments = scene
    rows = dp.decisive_queries(queries, points, judgments)
    rejudged = [
        dp.Rejudge(
            label="v1",
            grades={("q01", "B1"): Judgment(query_id="q01", author_id="B1", grade=1)},
        ),
        dp.Rejudge(
            label="v2",
            grades={("q01", "B1"): Judgment(query_id="q01", author_id="B1", grade=2)},
        ),
    ]
    text = dp.render_decisive_section(rows, points, judgments, rejudged)
    assert "**было** → **v1** → **v2**" in text
    assert "2 → 1 → 2 ⚠" in text, "все три колонки в одной строке, ⚠ за любое расхождение"
    assert "2 → ? → ?" in text, "пары вне пула пересуда видны как «?», а не как нули"


def test_rejudge_parse_takes_label_and_path(dp, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """`--rejudged v2=path` — метка колонки отделяется от пути (#114)."""
    path = tmp_path / "judgments_rejudge_x.jsonl"
    path.write_text(
        json.dumps({"query_id": "q01", "author_id": "A1", "grade": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    labelled = dp.Rejudge.parse(f"v2={path}")
    assert labelled.label == "v2" and labelled.grades[("q01", "A1")].grade == 1
    assert dp.Rejudge.parse(str(path)).label == "judgments_rejudge_x"


def test_review_file_joins_both_parts(dp) -> None:  # type: ignore[no-untyped-def]
    """`make review-sfr5c` собирает файл целиком: один H1, две части (#114)."""
    text = dp.render_review_file("# Решающие пары\n\nтело раздела\n", "# Выборка\n\n1. пара\n")
    assert text.count("\n# ") == 0 and text.startswith("# Судейские оценки SFR-5c")
    assert "## Часть 1. Решающие пары трёх точек" in text
    assert "## Часть 2. Случайная выборка новой партии" in text
    assert "тело раздела" in text and "1. пара" in text
    assert "Часть 2" not in dp.render_review_file("# Решающие пары\n\nтело\n", None)
