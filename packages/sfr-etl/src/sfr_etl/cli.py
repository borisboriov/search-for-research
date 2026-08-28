"""`sfr` CLI: institutions resolve, ETL steps, export, report."""

from typing import Annotated

import structlog
import typer
from sqlalchemy import select

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Institution
from sfr_core.settings import Settings, get_settings
from sfr_etl.client import OpenAlexClient
from sfr_etl.ingest import ingest_authors, short_id, upsert_institution

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

    with session_scope(engine) as session:
        institutions = list(session.execute(select(Institution)).scalars())
        target = _select_institution(institutions, institution)
        stats = ingest_authors(session, client, target, settings, max_authors=max)
    typer.echo(
        f"Ingested {stats['total']} authors "
        f"({stats['candidates']} supervisor candidates) "
        f"[network={client.n_network_requests}, cache_hits={client.n_cache_hits}]"
    )


if __name__ == "__main__":  # pragma: no cover
    app()
