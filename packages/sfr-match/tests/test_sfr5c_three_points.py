"""Три точки каталога (`scripts/sfr5c_three_points.py`): логика на синтетике.

Проверяется то, чего нет у предшественника: две дельты от **одной** базы,
подстановка пересуженных оценок и таблица расхождений между судьями. Скрипт
лежит вне пакетов — грузится по пути от корня репозитория, как и тест SFR-5b.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from sfr_match.evalset import Judgment, Query
from sfr_match.evaluate import QueryRun, Run

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.fixture(scope="module")
def tp():  # type: ignore[no-untyped-def]
    # sfr5c_three_points импортирует sfr5b_decision_metrics по имени файла.
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "sfr5c_three_points", SCRIPTS / "sfr5c_three_points.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
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


def _judgment(qid: str, aid: str, grade: int, **extra: str) -> Judgment:
    return Judgment(query_id=qid, author_id=aid, grade=grade, **extra)


@pytest.fixture
def scene(tp):  # type: ignore[no-untyped-def]
    """База 5 538, потолок и полный каталог на одном запросе — минимальная сцена."""
    golden = [Query(id="q01", text="запрос", expect="in-domain")]
    base = tp.Point(
        name="база",
        golden=_run("base", {"q01": [("OLD1", 0.50), ("OLD2", 0.45)]}),
        ood=_run("base", {"o01": [("OLD1", 0.20)]}),
        external=None,
        catalogue=tp.Catalogue({"OLD1": "МФТИ", "OLD2": "МГУ"}),
        aliases=tp.Aliases(),
        thresholds={"none": 0.32, "weak": 0.40, "high": 0.47},
    )
    cap = tp.Point(
        name="потолок",
        golden=_run("cap", {"q01": [("CAP1", 0.55), ("OLD1", 0.50)]}),
        ood=_run("cap", {"o01": [("CAP1", 0.22)]}),
        external=None,
        catalogue=tp.Catalogue({"OLD1": "МФТИ", "OLD2": "МГУ", "CAP1": "ВШЭ"}),
        aliases=tp.Aliases(),
        thresholds=None,  # свежий индекс ещё не проштампован
    )
    full = tp.Point(
        name="полный",
        golden=_run("full", {"q01": [("NEW9", 0.60), ("CAP1", 0.55)]}),
        ood=_run("full", {"o01": [("NEW9", 0.25)]}),
        external=None,
        catalogue=tp.Catalogue({"OLD1": "МФТИ", "CAP1": "ВШЭ", "NEW9": "МГУ"}),
        aliases=tp.Aliases(),
        thresholds={"none": 0.33, "weak": 0.40, "high": 0.49},
    )
    ood = [Query(id="o01", text="посторонний", expect="out-of-domain")]
    return golden, ood, base, cap, full


def test_two_deltas_share_one_base(tp, scene) -> None:  # type: ignore[no-untyped-def]
    golden, ood, base, cap, full = scene
    judgments = {
        ("q01", "OLD1"): _judgment("q01", "OLD1", 2),
        ("q01", "OLD2"): _judgment("q01", "OLD2", 0),
        ("q01", "CAP1"): _judgment("q01", "CAP1", 2),
        ("q01", "NEW9"): _judgment("q01", "NEW9", 0),
    }
    payload = tp.three_points(
        base=base,
        cap=cap,
        full=full,
        golden=golden,
        external=[],
        ood=ood,
        judgments=judgments,
    )
    assert list(payload["points"]) == ["база", "потолок", "полный"]
    assert payload["points"]["потолок"]["profiles"] == 3
    assert payload["points"]["потолок"]["thresholds"] is None
    # S@1 «было» одинаков в обеих дельтах — это и значит «одна база».
    cap_set = payload["delta"]["потолок"]["sets"]["golden_in_domain_24"]
    full_set = payload["delta"]["полный"]["sets"]["golden_in_domain_24"]
    assert cap_set["success_at_1"]["before"] == full_set["success_at_1"]["before"] == 1.0
    # Потолок: новый CAP1 с оценкой 2 встал первым — S@1 держится.
    assert cap_set["success_at_1"]["after"] == 1.0
    # Полный каталог: топ-1 занял новый с оценкой 0 — S@1 просел.
    assert full_set["success_at_1"]["after"] == 0.0
    assert full_set["displacement"]["entrants_new_grade_le1"] == 1


def test_rejudged_grades_override_and_diff_is_reported(tp, scene) -> None:  # type: ignore[no-untyped-def]
    golden, ood, base, cap, full = scene
    judgments = {
        ("q01", "OLD1"): _judgment("q01", "OLD1", 2, iteration="SFR-5"),
        ("q01", "CAP1"): _judgment("q01", "CAP1", 2, rationale="прямое совпадение"),
    }
    rejudged = {
        ("q01", "CAP1"): _judgment(
            "q01", "CAP1", 1, rationale="смежная тема", judge="fable (sfr-judge)"
        ),
        ("q01", "NEW9"): _judgment("q01", "NEW9", 2, judge="fable (sfr-judge)"),
    }
    merged = tp.overlay_judgments(judgments, rejudged)
    assert merged[("q01", "CAP1")].grade == 1, "пересуд перекрывает прежнюю оценку"
    assert merged[("q01", "OLD1")].grade == 2, "нетронутые пары остаются как были"

    diff = tp.rejudge_diff(judgments, rejudged)
    assert [(r["author_id"], r["grade_before"], r["grade_after"]) for r in diff] == [
        ("CAP1", 2, 1),
        ("NEW9", None, 2),
    ]
    assert diff[0]["judge_after"] == "fable (sfr-judge)"
    table = tp.render_rejudge_table(diff)
    assert "Расхождений: **2**" in table and "смежная тема" in table
    assert "Расхождений с прежними оценками нет" in tp.render_rejudge_table([])

    # Подстановка меняет метрику: у потолка топ-1 больше не grade 2.
    with_rejudged = tp.three_points(
        base=base,
        cap=cap,
        full=full,
        golden=golden,
        external=[],
        ood=ood,
        judgments=merged,
    )
    assert (
        with_rejudged["delta"]["потолок"]["sets"]["golden_in_domain_24"]["success_at_1"]["after"]
        == 0.0
    )


def test_table_has_three_rows_per_set_and_all_universities(tp, scene) -> None:  # type: ignore[no-untyped-def]
    golden, ood, base, cap, full = scene
    payload = tp.three_points(
        base=base,
        cap=cap,
        full=full,
        golden=golden,
        external=[],
        ood=ood,
        judgments={("q01", "OLD1"): _judgment("q01", "OLD1", 2)},
    )
    table = tp.render_three_points(payload, title="Проверка")
    rows = [line for line in table.splitlines() if line.startswith("| golden in-domain, 24 |")]
    assert len(rows) == 3, "на каждый набор — три строки: база и две точки"
    assert rows[0].count("—") >= 6, "у базы относительных метрик нет"
    # Вузы всех трёх колонок — в одной таблице, включая тот, что есть только у базы.
    assert "| МГУ |" in table and "| ВШЭ |" in table and "| МФТИ |" in table
    assert "не проштампованы" in table, "пороги свежего индекса — честное «нет»"
    assert "`cap`" in table and "`full`" in table


def test_base_caveat_names_unmerged_profiles(tp, scene) -> None:  # type: ignore[no-untyped-def]
    """Расклеенные 26.09 профили в базе отсутствуют — отчёт обязан их назвать."""
    golden, ood, base, cap, full = scene
    payload = tp.three_points(
        base=base,
        cap=cap,
        full=full,
        golden=golden,
        external=[],
        ood=ood,
        judgments={},
    )
    assert payload["base_caveat"]["unmerged_2026_09_26"] == list(tp.UNMERGED_2609)
    assert payload["base_caveat"]["profiles_in_base_export"] == 2


def test_read_thresholds_handles_missing_and_present(tp, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    assert tp.read_thresholds(tmp_path) is None
    (tmp_path / "meta.json").write_text('{"n_profiles": 9}', encoding="utf-8")
    assert tp.read_thresholds(tmp_path) is None
    (tmp_path / "meta.json").write_text(
        '{"thresholds": {"none": 0.31, "weak": 0.4, "high": 0.48}}', encoding="utf-8"
    )
    assert tp.read_thresholds(tmp_path) == {"none": 0.31, "weak": 0.4, "high": 0.48}
