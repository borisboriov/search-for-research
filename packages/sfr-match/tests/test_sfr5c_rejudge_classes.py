"""Классы расхождений судей (`scripts/sfr5c_rejudge_classes.py`) — на синтетике.

Оракулы, а не фиксация вывода: важно, что «строже» и «мягче» не путаются
местами, что пара без прежней оценки не считается суждением судьи и что доля
берётся от пар, оценённых в обеих разметках.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from sfr_match.evalset import Judgment

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.fixture(scope="module")
def mod():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "sfr5c_rejudge_classes", SCRIPTS / "sfr5c_rejudge_classes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _marks(pairs: dict[tuple[str, str], int]) -> dict[tuple[str, str], Judgment]:
    return {
        key: Judgment(query_id=key[0], author_id=key[1], grade=grade)
        for key, grade in pairs.items()
    }


def test_classify_names_the_transition(mod) -> None:  # type: ignore[no-untyped-def]
    assert mod.classify(2, 1) == "2→1"
    assert mod.classify(1, 1) == "="
    assert mod.classify(None, 0) == "нет→0"


@pytest.mark.parametrize(
    ("label", "stricter", "softer"),
    [("2→1", True, False), ("1→0", True, False), ("1→2", False, True), ("0→2", False, True)],
)
def test_direction_is_not_mixed_up(mod, label, stricter, softer) -> None:  # type: ignore[no-untyped-def]
    assert mod.is_stricter(label) is stricter
    assert mod.is_softer(label) is softer


def test_missing_and_equal_are_neither_stricter_nor_softer(mod) -> None:  # type: ignore[no-untyped-def]
    for label in ("=", "нет→2", "нет→0"):
        assert not mod.is_stricter(label)
        assert not mod.is_softer(label)


def test_compare_counts_classes_and_share(mod) -> None:  # type: ignore[no-untyped-def]
    before = _marks({("q1", "A1"): 2, ("q1", "A2"): 1, ("q2", "A3"): 0})
    after = _marks({("q1", "A1"): 1, ("q1", "A2"): 1, ("q2", "A3"): 2, ("q2", "A4"): 2})
    result = mod.compare(before, after)
    assert result["pairs"] == 4
    # A4 не была оценена раньше: она не суждение судьи и в знаменатель не идёт.
    assert result["judged_in_both"] == 3
    assert result["disagreements"] == 2
    assert result["share"] == pytest.approx(2 / 3, abs=1e-4)
    assert result["stricter"] == 1
    assert result["softer"] == 1
    assert result["classes"] == {"2→1": 1, "=": 1, "0→2": 1, "нет→2": 1}
    assert result["per_query"] == {"q1": {"2→1": 1}, "q2": {"0→2": 1, "нет→2": 1}}


def test_keys_fix_the_comparison_set(mod) -> None:  # type: ignore[no-untyped-def]
    """Три сравнения считаются по одному множеству пар — иначе доли несравнимы."""
    before = _marks({("q1", "A1"): 2, ("q1", "A2"): 2})
    after = _marks({("q1", "A1"): 1})
    result = mod.compare(before, after, keys=[("q1", "A1"), ("q1", "A2")])
    assert result["pairs"] == 2
    assert result["judged_in_both"] == 1
    assert result["disagreements"] == 1


def test_render_is_one_table_row(mod) -> None:  # type: ignore[no-untyped-def]
    row = mod.render("v1 ↔ v2", mod.compare(_marks({("q1", "A1"): 1}), _marks({("q1", "A1"): 2})))
    assert row.startswith("| v1 ↔ v2 |")
    assert "1→2 ×1" in row
