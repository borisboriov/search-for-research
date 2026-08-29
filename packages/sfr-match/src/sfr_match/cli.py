"""`sfr-match` CLI: index, search, eval, report (SPEC_SFR1 §2)."""

import json
import time
from pathlib import Path
from typing import Annotated

import structlog
import typer

from sfr_match.composition import COMPOSITIONS, Composition
from sfr_match.evalset import (
    eval_dir,
    load_judgments,
    load_queries,
    query_set_path,
    write_jsonl,
)
from sfr_match.evaluate import (
    DEFAULT_RUNS_DIR,
    POOL_DEPTH,
    build_pool,
    load_runs,
    run_queries,
    save_run,
)
from sfr_match.index import DEFAULT_INDEX_ROOT, build_index, index_path, load_docs
from sfr_match.models import DEFAULT_MODELS, resolve_model
from sfr_match.profiles import DEFAULT_PROFILES_PATH, load_profiles
from sfr_match.report import (
    NOTES_PATH,
    REPORT_PATH,
    compute_metrics,
    read_notes,
    render_report,
    sample_for_review,
)
from sfr_match.search import load_backend

log = structlog.get_logger(__name__)

app = typer.Typer(no_args_is_help=True, help="Search For Research matching (SFR-1)")

ModelOpt = Annotated[str, typer.Option("--model", "-m", help="Model key or HuggingFace id")]
CleanOpt = Annotated[bool, typer.Option("--clean/--no-clean", help="Apply profile-text cleaning")]
ProfilesOpt = Annotated[Path, typer.Option("--profiles", help="Path to profiles.jsonl")]
ComposeOpt = Annotated[
    str, typer.Option("--compose", help=f"What goes into the index: {', '.join(COMPOSITIONS)}")
]


def _compose(value: str) -> Composition:
    if value not in COMPOSITIONS:
        raise _fail(f"unknown --compose {value!r}; known: {', '.join(COMPOSITIONS)}")
    return value


def _fail(message: str) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=True)
    return typer.Exit(code=1)


@app.command()
def index(
    model: ModelOpt = "e5-base",
    clean: CleanOpt = False,
    profiles_path: ProfilesOpt = DEFAULT_PROFILES_PATH,
    index_root: Annotated[Path, typer.Option("--index-root")] = DEFAULT_INDEX_ROOT,
    compose: ComposeOpt = "full",
) -> None:
    """Build a search index from profiles.jsonl."""
    mode = _compose(compose)
    try:
        spec = resolve_model(model)
        records = load_profiles(profiles_path, clean=clean, compose=mode)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise _fail(str(exc)) from exc
    out_dir = index_path(spec, clean=clean, compose=mode, root=index_root)
    meta = build_index(records, spec, clean=clean, out_dir=out_dir, compose=mode)
    typer.secho(
        f"{meta.slug}: {meta.n_profiles} профилей, dim={meta.dim}, "
        f"{meta.build_seconds:.1f} c → {out_dir} ({meta.version})",
        fg=typer.colors.GREEN,
    )


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Запрос студента, свободный текст")],
    model: ModelOpt = "e5-base",
    clean: CleanOpt = False,
    k: Annotated[int, typer.Option("-k", "--top", help="Сколько НР показать")] = 10,
    index_root: Annotated[Path, typer.Option("--index-root")] = DEFAULT_INDEX_ROOT,
) -> None:
    """Search supervisors for a free-text query."""
    try:
        spec = resolve_model(model)
        backend = load_backend(index_path(spec, clean=clean, root=index_root), spec.key)
    except (KeyError, FileNotFoundError) as exc:
        raise _fail(str(exc)) from exc
    backend.warmup()  # model loading is not part of query latency
    started = time.perf_counter()
    hits = backend.search(query, k=k)
    elapsed_ms = (time.perf_counter() - started) * 1000

    typer.secho(f"\n«{query}» — {spec.slug(clean=clean)}, {elapsed_ms:.0f} мс\n", bold=True)
    for hit in hits:
        typer.secho(f"{hit.rank:>2}. {hit.name}  ", nl=False, bold=True)
        typer.secho(f"score={hit.score:.4f}  [{hit.author_id}]", fg=typer.colors.BRIGHT_BLACK)
        if hit.topics:
            typer.echo(f"    {'; '.join(hit.topics[:4])}")


@app.command(name="eval")
def eval_cmd(
    models: Annotated[str, typer.Option("--models", help="Comma-separated model keys")] = ",".join(
        DEFAULT_MODELS
    ),
    clean: Annotated[
        bool | None,
        typer.Option("--clean/--no-clean", help="Only the clean (or only the raw) variants"),
    ] = None,
    k: Annotated[int, typer.Option("--k")] = 10,
    index_root: Annotated[Path, typer.Option("--index-root")] = DEFAULT_INDEX_ROOT,
    runs_dir: Annotated[Path, typer.Option("--runs-dir")] = DEFAULT_RUNS_DIR,
    compose: ComposeOpt = "full",
    queries_set: Annotated[
        str, typer.Option("--queries", help="Query set: golden | ood | external")
    ] = "golden",
) -> None:
    """Run a query set against every model/variant and store the rankings."""
    mode = _compose(compose)
    variants = [(name.strip(), False) for name in models.split(",") if name.strip()]
    if clean is True:
        variants = [(name, True) for name, _ in variants]
    elif clean is None:
        pass
    try:
        queries = load_queries(query_set_path(queries_set))
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(str(exc)) from exc
    if not queries:
        raise _fail(f"набор запросов {queries_set!r} пуст — заполнять его людям, не агенту")

    for name, use_clean in variants:
        spec = resolve_model(name)
        directory = index_path(spec, clean=use_clean, compose=mode, root=index_root)
        if not (directory / "meta.json").exists():
            raise _fail(f"нет индекса {directory} — сначала `sfr-match index -m {name}`")
        backend = load_backend(directory, spec.key)
        run = run_queries(backend, queries, k=k)
        path = save_run(run, runs_dir)
        typer.secho(
            f"{run.variant}: {len(run.results)} запросов, "
            f"средняя латентность {sum(run.latencies) / len(run.latencies):.0f} мс → {path}",
            fg=typer.colors.GREEN,
        )


@app.command()
def pool(
    runs_dir: Annotated[Path, typer.Option("--runs-dir")] = DEFAULT_RUNS_DIR,
    depth: Annotated[int, typer.Option("--depth")] = POOL_DEPTH,
    out: Annotated[Path, typer.Option("--out")] = Path("data/eval/pool.jsonl"),
    index_root: Annotated[Path, typer.Option("--index-root")] = DEFAULT_INDEX_ROOT,
    queries_set: Annotated[
        str, typer.Option("--queries", help="Query set: golden | ood | external")
    ] = "golden",
) -> None:
    """Emit the judging pool: unique (query, author) pairs sorted by author id.

    Sorted by author — not by score — so the judge cannot tell which model
    produced a pair (SPEC_SFR1 §5.2).
    """
    try:
        runs = load_runs(runs_dir)
        queries = {query.id: query for query in load_queries(query_set_path(queries_set))}
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(str(exc)) from exc
    docs_dir = next((d for d in sorted(index_root.iterdir()) if (d / "docs.json").exists()), None)
    if docs_dir is None:
        raise _fail(f"нет ни одного индекса в {index_root}")
    docs = {str(doc["id"]): doc for doc in load_docs(docs_dir)}
    pairs = build_pool(runs, depth=depth)
    existing = load_judgments() if (eval_dir() / "judgments.jsonl").exists() else {}
    records = [
        {
            "query_id": query_id,
            "author_id": author_id,
            "query": queries[query_id].text,
            "expect": queries[query_id].expect,
            "name": docs[author_id]["name"],
            "topics": docs[author_id]["topics"],
            "profile_text": docs[author_id]["profile_text"],
            "judged": (query_id, author_id) in existing,
        }
        for query_id, author_id in pairs
        if query_id in queries and author_id in docs
    ]
    write_jsonl(out, records)
    todo = sum(1 for record in records if not record["judged"])
    typer.secho(f"пул: {len(records)} пар, неоценённых {todo} → {out}", fg=typer.colors.GREEN)


@app.command(name="review-sample")
def review_sample(
    n: Annotated[int, typer.Option("--n")] = 20,
    runs_dir: Annotated[Path, typer.Option("--runs-dir")] = DEFAULT_RUNS_DIR,
    index_root: Annotated[Path, typer.Option("--index-root")] = DEFAULT_INDEX_ROOT,
) -> None:
    """Write eval/judgments_for_review.md — a random sample for human re-check."""
    try:
        runs = load_runs(runs_dir)
        queries = load_queries()
        judgments = load_judgments()
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(str(exc)) from exc
    docs_dir = next((d for d in sorted(index_root.iterdir()) if (d / "docs.json").exists()), None)
    if docs_dir is None:
        raise _fail(f"нет ни одного индекса в {index_root}")
    profiles = {str(doc["id"]): doc for doc in load_docs(docs_dir)}
    pool_pairs = [pair for pair in build_pool(runs) if pair in judgments]
    out = eval_dir() / "judgments_for_review.md"
    out.write_text(
        sample_for_review(pool_pairs, queries, judgments, profiles, n=n), encoding="utf-8"
    )
    typer.secho(f"{n} пар → {out}", fg=typer.colors.GREEN)


@app.command()
def report(
    runs_dir: Annotated[Path, typer.Option("--runs-dir")] = DEFAULT_RUNS_DIR,
    out: Annotated[Path, typer.Option("--out")] = REPORT_PATH,
    notes: Annotated[Path, typer.Option("--notes")] = NOTES_PATH,
) -> None:
    """Combine runs and judgments into docs/SFR1_REPORT.md."""
    try:
        runs = load_runs(runs_dir)
        queries = load_queries()
        judgments = load_judgments()
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(str(exc)) from exc
    metrics = [compute_metrics(run, queries, judgments) for run in runs]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(metrics, queries, judgments, read_notes(notes)), encoding="utf-8")
    typer.secho(f"отчёт: {len(metrics)} вариантов → {out}", fg=typer.colors.GREEN)


@app.command()
def stats(profiles_path: ProfilesOpt = DEFAULT_PROFILES_PATH) -> None:
    """Show what the cleaning preprocessor changes on the current corpus."""
    raw = load_profiles(profiles_path, clean=False)
    cleaned = load_profiles(profiles_path, clean=True)
    changed = [
        (r.name, len(r.indexed_text) - len(c.indexed_text))
        for r, c in zip(raw, cleaned, strict=True)
        if r.indexed_text != c.indexed_text
    ]
    typer.echo(
        json.dumps(
            {
                "profiles": len(raw),
                "changed_by_cleaning": len(changed),
                "chars_removed_total": sum(delta for _, delta in changed),
                "top_changed": sorted(changed, key=lambda pair: -pair[1])[:5],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
