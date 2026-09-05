"""Golden set / judgments: schema validation, id uniqueness, and the shipped files."""

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from sfr_match.evalset import Query, eval_dir, load_judgments, load_queries, write_jsonl


def test_shipped_golden_set_has_30_queries_in_the_required_mix() -> None:
    queries = load_queries()
    assert len(queries) == 30
    counts = Counter(query.expect for query in queries)
    assert counts["in-domain"] == 22
    assert counts["edge"] == 4
    assert counts["out-of-domain"] == 4


def test_shipped_golden_set_ids_are_unique_and_texts_non_trivial() -> None:
    queries = load_queries()
    assert len({query.id for query in queries}) == len(queries)
    assert all(len(query.text) >= 5 for query in queries)


def test_unknown_expect_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Query.model_validate({"id": "q1", "text": "нейросети", "expect": "maybe"})


def test_grade_outside_0_2_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "judgments.jsonl"
    write_jsonl(path, [{"query_id": "q1", "author_id": "A1", "grade": 3}])
    with pytest.raises(ValidationError):
        load_judgments(path)


def test_duplicate_query_id_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "queries.jsonl"
    record = {"id": "q1", "text": "нейросети", "expect": "in-domain"}
    write_jsonl(path, [record, dict(record)])
    with pytest.raises(ValueError, match="duplicate query id"):
        load_queries(path)


def test_duplicate_judgment_pair_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "judgments.jsonl"
    record = {"query_id": "q1", "author_id": "A1", "grade": 2}
    write_jsonl(path, [record, dict(record)])
    with pytest.raises(ValueError, match="duplicate judgment"):
        load_judgments(path)


def test_malformed_json_reports_the_line_number(tmp_path: Path) -> None:
    path = tmp_path / "queries.jsonl"
    good = '{"id": "q1", "text": "нейросети", "expect": "edge"}'
    path.write_text(f"{good}\nnot json\n", encoding="utf-8")
    with pytest.raises(ValueError, match=":2:"):
        load_queries(path)


def test_missing_file_names_the_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_queries(tmp_path / "nope.jsonl")


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "queries.jsonl"
    path.write_text('\n{"id": "q1", "text": "нейросети", "expect": "edge"}\n\n', encoding="utf-8")
    assert len(load_queries(path)) == 1


def test_write_jsonl_keeps_cyrillic_readable(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    write_jsonl(path, [{"text": "нейросети"}])
    assert "нейросети" in path.read_text(encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["text"] == "нейросети"


def test_eval_dir_points_at_the_versioned_package_data() -> None:
    assert eval_dir().name == "eval"
    assert (eval_dir() / "queries.jsonl").exists()


def test_judgment_iteration_is_optional_and_backward_compatible(tmp_path: Path) -> None:
    """Метка итерации (SFR-5) не должна ломать чтение оценок прошлых итераций."""
    path = tmp_path / "judgments.jsonl"
    path.write_text(
        '{"query_id": "q1", "author_id": "A1", "grade": 2, "rationale": "прямое"}\n'
        '{"query_id": "q2", "author_id": "A2", "grade": 1, "rationale": "смежное",'
        ' "iteration": "sfr5"}\n',
        encoding="utf-8",
    )
    judgments = load_judgments(path)
    assert judgments[("q1", "A1")].iteration == "", "строка без поля читается как прежде"
    assert judgments[("q2", "A2")].iteration == "sfr5"


def test_real_judgments_carry_the_sfr5_batch() -> None:
    """В версионируемом наборе партия SFR-5 размечена — на ней стоит выборка на проверку."""
    judgments = load_judgments()
    marked = [j for j in judgments.values() if j.iteration == "sfr5"]
    assert len(marked) == 83
