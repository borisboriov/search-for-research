"""`sfr` CLI: institutions resolve, ETL steps, export, report."""

import json
import time
from pathlib import Path
from typing import Annotated

import structlog
import typer
from sqlalchemy import select

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Institution
from sfr_core.settings import Settings, get_settings
from sfr_etl.client import OpenAlexClient
from sfr_etl.export import export_cards_jsonl, export_profiles_jsonl
from sfr_etl.ingest import ingest_authors, short_id, upsert_institution
from sfr_etl.profiles import build_profiles
from sfr_etl.report import (
    cache_size_info,
    compute_stats,
    read_notes,
    read_run_stats,
    render_report,
    sample_profiles,
)
from sfr_etl.works import ingest_works

log = structlog.get_logger(__name__)

app = typer.Typer(no_args_is_help=True, help="Search For Research ETL")
institutions_app = typer.Typer(no_args_is_help=True, help="Institution management")
etl_app = typer.Typer(no_args_is_help=True, help="ETL pipeline steps")
export_app = typer.Typer(no_args_is_help=True, help="Data exports")
app.add_typer(institutions_app, name="institutions")
app.add_typer(etl_app, name="etl")
app.add_typer(export_app, name="export")


def _load_settings() -> Settings:
    try:
        return get_settings()
    except Exception as exc:
        typer.secho(f"Configuration error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


def _make_client(settings: Settings, refresh: bool) -> OpenAlexClient:
    return OpenAlexClient(
        settings.openalex_mailto,
        base_url=settings.openalex_base_url,
        max_rps=settings.openalex_max_rps,
        cache_dir=settings.raw_cache_dir,
        refresh=refresh,
    )


def _record_run_stats(
    settings: Settings, step: str, seconds: float, client: OpenAlexClient | None = None
) -> None:
    """Append per-step run metadata (for `sfr report`).

    History is kept, not overwritten: the report shows the cold first run and the
    latest (cache-warm) one, which is exactly what the DoD asks about.
    """
    path = settings.data_dir / "run_stats.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = read_run_stats(path)
    entry: dict[str, object] = {"seconds": round(seconds, 1)}
    if client is not None:
        entry["network"] = client.n_network_requests
        entry["cache_hits"] = client.n_cache_hits
    history = stats.get(step)
    if not isinstance(history, list):
        history = [history] if history else []
    history.append(entry)
    stats[step] = history
    path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")


def _select_institution(session_institutions: list[Institution], wanted: str | None) -> Institution:
    if wanted is not None:
        wanted_short = short_id(wanted)
        for institution in session_institutions:
            if institution.openalex_id == wanted_short:
                return institution
        typer.secho(
            f"Institution {wanted!r} not found in DB. Run `sfr institutions resolve` first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    if len(session_institutions) == 1:
        return session_institutions[0]
    typer.secho(
        "Expected exactly one institution in DB (or pass --institution). "
        f"Found: {[i.openalex_id for i in session_institutions]}. "
        "Run `sfr institutions resolve` first.",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(code=1)


@institutions_app.command("resolve")
def institutions_resolve(
    query: Annotated[str, typer.Argument(help="Institution name to search for")],
    pick: Annotated[int, typer.Option(help="1-based index of the candidate to save")] = 1,
    refresh: Annotated[bool, typer.Option("--refresh", help="Bypass the raw cache")] = False,
) -> None:
    """Search OpenAlex for an institution, list candidates, save the picked one to the DB."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    client = _make_client(settings, refresh)

    body = client.get("/institutions", {"search": query})
    results = body.get("results", [])
    if not results:
        typer.secho(f"No institutions found for {query!r}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Candidates for {query!r}:")
    for i, record in enumerate(results[:10], start=1):
        marker = "→" if i == pick else " "
        typer.echo(
            f" {marker} {i}. {short_id(record['id'])}  {record['display_name']} "
            f"({record.get('country_code')}, works={record.get('works_count')})"
        )
    if not 1 <= pick <= len(results):
        typer.secho(f"--pick {pick} is out of range", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    chosen = results[pick - 1]
    engine = make_engine(settings.sfr_db_url)
    with session_scope(engine) as session:
        institution = upsert_institution(session, chosen)
        typer.echo(f"Saved: {institution.openalex_id} — {institution.name_en}")


@etl_app.command("authors")
def etl_authors(
    institution: Annotated[
        str | None, typer.Option(help="OpenAlex institution ID (defaults to the only one in DB)")
    ] = None,
    max: Annotated[int, typer.Option(help="Max authors to ingest")] = 300,
    refresh: Annotated[bool, typer.Option("--refresh", help="Bypass the raw cache")] = False,
) -> None:
    """Ingest authors affiliated with the institution (sorted by works_count desc)."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    client = _make_client(settings, refresh)
    engine = make_engine(settings.sfr_db_url)

    started = time.monotonic()
    with session_scope(engine) as session:
        institutions = list(session.execute(select(Institution)).scalars())
        target = _select_institution(institutions, institution)
        stats = ingest_authors(session, client, target, settings, max_authors=max)
    _record_run_stats(settings, "etl authors", time.monotonic() - started, client)
    typer.echo(
        f"Ingested {stats['total']} authors "
        f"({stats['candidates']} supervisor candidates) "
        f"[network={client.n_network_requests}, cache_hits={client.n_cache_hits}]"
    )


@etl_app.command("works")
def etl_works(
    since_years: Annotated[int | None, typer.Option(help="Recency window in years")] = None,
    per_author: Annotated[int | None, typer.Option(help="Max works stored per author")] = None,
    refresh: Annotated[bool, typer.Option("--refresh", help="Bypass the raw cache")] = False,
) -> None:
    """Ingest works (recent + most cited) for all supervisor candidates."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    client = _make_client(settings, refresh)
    engine = make_engine(settings.sfr_db_url)

    started = time.monotonic()
    with session_scope(engine) as session:
        totals = ingest_works(
            session,
            client,
            since_years=since_years if since_years is not None else settings.works_since_years,
            per_author=per_author if per_author is not None else settings.works_per_author,
        )
    _record_run_stats(settings, "etl works", time.monotonic() - started, client)
    typer.echo(
        f"Ingested {totals['works']} works for {totals['authors']} candidates "
        f"({totals['with_abstract']} with abstract) "
        f"[network={client.n_network_requests}, cache_hits={client.n_cache_hits}]"
    )


@etl_app.command("build-profiles")
def etl_build_profiles() -> None:
    """Build SupervisorProfile (profile_text + completeness) for every candidate."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    engine = make_engine(settings.sfr_db_url)
    started = time.monotonic()
    with session_scope(engine) as session:
        stats = build_profiles(session, settings)
    _record_run_stats(settings, "etl build-profiles", time.monotonic() - started)
    typer.echo(
        f"Built {stats['profiles']} profiles "
        f"({stats['in_range']} within 300–1500 chars, "
        f"{stats['without_works']} candidates without works)"
    )


@export_app.command("jsonl")
def export_jsonl(
    out: Annotated[Path, typer.Option(help="Output JSONL path")] = Path(
        "data/exports/profiles.jsonl"
    ),
) -> None:
    """Export one JSON line per supervisor profile (input for SFR-1 embeddings)."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    engine = make_engine(settings.sfr_db_url)
    started = time.monotonic()
    with session_scope(engine) as session:
        n_lines = export_profiles_jsonl(session, out)
    _record_run_stats(settings, "export jsonl", time.monotonic() - started)
    typer.echo(f"Exported {n_lines} profiles to {out}")


@export_app.command("cards")
def export_cards(
    out: Annotated[Path, typer.Option(help="Output JSONL path")] = Path("data/exports/cards.jsonl"),
) -> None:
    """Export card enrichment for the API (SFR-3): citations + top works per supervisor."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    engine = make_engine(settings.sfr_db_url)
    started = time.monotonic()
    with session_scope(engine) as session:
        n_lines = export_cards_jsonl(session, out)
    _record_run_stats(settings, "export cards", time.monotonic() - started)
    typer.echo(f"Exported {n_lines} cards to {out}")


@app.command("report")
def report(
    out: Annotated[Path, typer.Option(help="Output Markdown path")] = Path("docs/REPORT.md"),
) -> None:
    """Generate the run report (docs/REPORT.md)."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    engine = make_engine(settings.sfr_db_url)
    with session_scope(engine) as session:
        stats = compute_stats(session)
        samples = sample_profiles(session)
    run_stats = read_run_stats(settings.data_dir / "run_stats.json")
    cache_files, cache_mb = cache_size_info(settings.raw_cache_dir)
    notes = read_notes(out.parent / "REPORT_notes.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_report(stats, samples, run_stats, cache_files, cache_mb, notes),
        encoding="utf-8",
    )
    typer.echo(f"Report written to {out}")


if __name__ == "__main__":  # pragma: no cover
    app()
