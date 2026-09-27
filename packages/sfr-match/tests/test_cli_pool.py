"""CLI: слепой судейский пул и выборка по отдельному файлу оценок.

Оба флага появились в сессии выкладки SFR-5c: пересуд топ-5 делает субагент
`sfr-judge`, и ему нельзя показывать ни прежние оценки, ни даже их наличие
(`JUDGE_RUBRIC.md`, п. 5), а выборка на проверку человеком собирается по файлу
этого пересуда, а не по накопленному `judgments.jsonl`.
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from sfr_match.cli import app
from sfr_match.evalset import Judgment, Query, load_queries, query_set_path, write_jsonl
from sfr_match.evaluate import run_queries, save_run
from sfr_match.index import build_index, index_path
from sfr_match.models import resolve_model
from sfr_match.profiles import ProfileRecord
from sfr_match.search import DenseBackend

runner = CliRunner()


def _scene(tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type) -> tuple[Path, Path]:
    """Индекс и прогон по первым трём запросам golden set — как на боевых путях."""
    spec = resolve_model("e5-base")
    index_root = tmp_path / "indexes"
    out_dir = index_path(spec, clean=False, root=index_root)
    build_index(profiles, spec, clean=False, out_dir=out_dir, embedder=fake_embedder(spec))
    backend = DenseBackend(out_dir, spec, embedder=fake_embedder(spec))
    run = run_queries(backend, load_queries(query_set_path("golden"))[:3], k=5)
    runs_dir = tmp_path / "runs"
    save_run(run, runs_dir)
    return index_root, runs_dir


def test_pool_blind_hides_that_a_pair_was_ever_judged(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    index_root, runs_dir = _scene(tmp_path, profiles, fake_embedder)
    out = tmp_path / "pool.jsonl"
    result = runner.invoke(
        app,
        [
            "pool",
            "--runs-dir",
            str(runs_dir),
            "--index-root",
            str(index_root),
            "--out",
            str(out),
            "--blind",
        ],
    )
    assert result.exit_code == 0, result.output
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line]
    assert records, "пул не должен быть пустым"
    assert all("judged" not in record for record in records), (
        "следа прежней разметки быть не должно"
    )
    # #131: без expect — метка набора подсказывает судье, что запрос «трудный»
    assert set(records[0]) == {
        "query_id",
        "author_id",
        "query",
        "name",
        "topics",
        "profile_text",
    }
    ids = [(r["query_id"], r["author_id"]) for r in records]
    assert ids == sorted(ids, key=lambda k: (k[1], k[0])), (
        "порядок — по author_id: пятёрка одного запроса подряд якорит судью"
    )
    assert len(ids) == len(set(ids)), "пара встречается один раз"
    assert "слепой пул" in result.output


def test_pool_without_blind_still_marks_judged_pairs(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    index_root, runs_dir = _scene(tmp_path, profiles, fake_embedder)
    out = tmp_path / "pool.jsonl"
    result = runner.invoke(
        app,
        ["pool", "--runs-dir", str(runs_dir), "--index-root", str(index_root), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line]
    assert all("judged" in record for record in records)
    ids = [(r["query_id"], r["author_id"]) for r in records]
    assert ids == sorted(ids), "обычный пул остаётся в порядке (запрос, автор)"


def test_review_sample_reads_the_judgments_file_it_is_given(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    index_root, runs_dir = _scene(tmp_path, profiles, fake_embedder)
    queries: list[Query] = load_queries(query_set_path("golden"))[:1]
    judgments = tmp_path / "judgments_deploy.jsonl"
    write_jsonl(
        judgments,
        [
            Judgment(
                query_id=queries[0].id,
                author_id="A1",
                grade=2,
                rationale="выдуманная пара для теста",
                iteration="test",
                judge="fable (sfr-judge)",
            ).model_dump()
        ],
    )
    out = tmp_path / "review.md"
    result = runner.invoke(
        app,
        [
            "review-sample",
            "--n",
            "5",
            "--runs-dir",
            str(runs_dir),
            "--index-root",
            str(index_root),
            "--judgments",
            str(judgments),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "выдуманная пара для теста" in text, "обоснования берутся из указанного файла"
    assert text.count("## ") == 1, "в файле оценок одна пара — в выборке тоже одна"


def test_review_sample_default_goes_to_gitignored_data_not_eval(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    # #143: без --out выборка ложится в data/eval/review — прежнее умолчание
    # eval/judgments_for_review.md переписало бы выборку SFR-1, проверенную Борисом.
    index_root, runs_dir = _scene(tmp_path, profiles, fake_embedder)
    queries: list[Query] = load_queries(query_set_path("golden"))[:1]
    judgments = tmp_path / "judgments.jsonl"
    write_jsonl(
        judgments,
        [
            Judgment(
                query_id=queries[0].id, author_id="A1", grade=2, rationale="тест", iteration="t"
            ).model_dump()
        ],
    )
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "queries.jsonl").write_bytes(query_set_path("golden").read_bytes())
    monkeypatch.setenv("SFR_MATCH_EVAL_DIR", str(eval_dir))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "review-sample",
            "--n",
            "5",
            "--runs-dir",
            str(runs_dir),
            "--index-root",
            str(index_root),
            "--judgments",
            str(judgments),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "data/eval/review/judgments_for_review.md").exists()
    assert not (eval_dir / "judgments_for_review.md").exists(), "в eval/ умолчание не пишет"


def test_eval_queries_file_runs_an_archived_query_set(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    # --queries-file — архивная редакция набора (19 посторонних до 26.09, #126):
    # прогон идёт ровно по файлу, а не по действующему набору того же имени.
    spec = resolve_model("e5-base")
    index_root = tmp_path / "indexes"
    out_dir = index_path(spec, clean=False, root=index_root)
    build_index(profiles, spec, clean=False, out_dir=out_dir, embedder=fake_embedder(spec))
    monkeypatch.setattr(
        "sfr_match.cli.load_backend",
        lambda directory, key: DenseBackend(directory, spec, embedder=fake_embedder(spec)),
    )
    archived = load_queries(query_set_path("ood"))[:2]
    queries_file = tmp_path / "ood_archived.jsonl"
    write_jsonl(queries_file, [q.model_dump() for q in archived])
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "eval",
            "--models",
            "e5-base",
            "--no-clean",
            "--index-root",
            str(index_root),
            "--runs-dir",
            str(runs_dir),
            "--queries-file",
            str(queries_file),
        ],
    )

    assert result.exit_code == 0, result.output
    run = json.loads(next(runs_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert [r["query_id"] for r in run["results"]] == [q.id for q in archived]


def test_eval_queries_file_missing_fails_loudly(tmp_path: Path) -> None:
    missing = tmp_path / "nope.jsonl"
    result = runner.invoke(app, ["eval", "--queries-file", str(missing)])
    assert result.exit_code != 0
    assert "nope.jsonl" in result.output


def test_stamp_judgments_adds_the_profile_fingerprint_from_the_pool(tmp_path: Path) -> None:
    # #123: отпечаток ставится после судейства из того же пула; строки вне пула
    # и уже проставленные не меняются.
    from sfr_match.evalset import profile_fingerprint

    pool = tmp_path / "pool.jsonl"
    write_jsonl(pool, [{"query_id": "q1", "author_id": "A1", "profile_text": "текст профиля"}])
    judgments = tmp_path / "judgments.jsonl"
    write_jsonl(
        judgments,
        [
            {"query_id": "q1", "author_id": "A1", "grade": 2, "judge": "fable (sfr-judge)"},
            {"query_id": "q1", "author_id": "A9", "grade": 0, "judge": "fable (sfr-judge)"},
            {"query_id": "q2", "author_id": "A1", "grade": 1, "profile_fp": "keep"},
        ],
    )
    result = runner.invoke(
        app, ["stamp-judgments", "--pool", str(pool), "--judgments", str(judgments)]
    )
    assert result.exit_code == 0, result.output
    rows = [json.loads(line) for line in judgments.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["profile_fp"] == profile_fingerprint("текст профиля")
    assert "profile_fp" not in rows[1]
    assert rows[2]["profile_fp"] == "keep"
    assert "проставлен 1, уже был 1, нет в пуле 1" in result.output
