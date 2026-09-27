"""`sfr` CLI: institutions resolve, ETL steps, export, report."""

import json
import time
from pathlib import Path
from typing import Annotated

import structlog
import typer
from sqlalchemy import func, select

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Author, Institution
from sfr_core.settings import Settings, get_settings
from sfr_etl.catalog import (
    DEFAULT_FIELD_FLOOR,
    fetch_candidate_pool,
    ingest_selected,
    stratified_select,
)
from sfr_etl.client import OpenAlexClient
from sfr_etl.dedup import (
    DEFAULT_DECISIONS_PATH,
    STATUS_FORBIDDEN_BUT_MERGED,
    STATUS_NOT_IN_CATALOGUE,
    DecisionsFileMissing,
    UnmergeError,
    apply_merges,
    detect_suspect_merges,
    find_splits,
    load_decisions_or_fail,
    recompute_merged_aggregates,
    render_dedup_review,
    suspect_examples,
    unmerge_author,
)
from sfr_etl.export import export_cards_jsonl, export_profiles_jsonl
from sfr_etl.ingest import ingest_authors, short_id, upsert_institution
from sfr_etl.orcid import OrcidClient, foreign_orcid_note
from sfr_etl.profiles import build_profiles
from sfr_etl.report import (
    cache_size_info,
    compute_stats,
    read_notes,
    read_run_stats,
    render_report,
    sample_profiles,
)
from sfr_etl.works import backfill_institutions_distinct_count, ingest_works

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
        api_key=settings.openalex_api_key,
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
    max: Annotated[int, typer.Option(help="Max authors to ingest (strategy=top)")] = 300,
    strategy: Annotated[
        str,
        typer.Option(
            help="top — верхушка по works_count (SFR-0); "
            "stratified — квота с раскладкой по областям OpenAlex (SFR-5)"
        ),
    ] = "top",
    quota: Annotated[
        int, typer.Option(help="Сколько авторов вуза оставить (strategy=stratified)")
    ] = 500,
    floor: Annotated[
        int, typer.Option(help="Минимум мест на область, если они у неё есть")
    ] = DEFAULT_FIELD_FLOOR,
    keep: Annotated[
        str | None,
        typer.Option(help="Author-ID через запятую: обязаны попасть в отбор (уже в каталоге)"),
    ] = None,
    keep_existing: Annotated[
        bool,
        typer.Option(
            "--keep-existing/--no-keep-existing",
            help="Сохранить авторов этого вуза, уже отмеченных кандидатами "
            "(на них стоят судейские оценки и превью лендинга)",
        ),
    ] = True,
    refresh: Annotated[bool, typer.Option("--refresh", help="Bypass the raw cache")] = False,
) -> None:
    """Ingest authors affiliated with the institution.

    ``top`` повторяет отбор SFR-0 (сортировка по works_count), ``stratified``
    набирает квоту с раскладкой по областям — см. `sfr_etl.catalog`.
    """
    if strategy not in {"top", "stratified"}:
        typer.secho(f"unknown --strategy {strategy!r}: top | stratified", fg="red", err=True)
        raise typer.Exit(code=1)
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    client = _make_client(settings, refresh)
    engine = make_engine(settings.sfr_db_url)
    keep_ids = [part.strip() for part in (keep or "").split(",") if part.strip()]

    started = time.monotonic()
    fields_line = ""
    with session_scope(engine) as session:
        institutions = list(session.execute(select(Institution)).scalars())
        target = _select_institution(institutions, institution)
        if strategy == "top":
            stats = ingest_authors(session, client, target, settings, max_authors=max)
        else:
            if keep_existing:
                keep_ids += [
                    author.openalex_id
                    for author in session.execute(
                        select(Author).where(
                            Author.is_supervisor_candidate.is_(True),
                            Author.last_known_institution_id == target.id,
                        )
                    ).scalars()
                ]
            pool = fetch_candidate_pool(client, target, settings)
            selected, sizes = stratified_select(
                pool, quota=quota, settings=settings, floor=floor, keep_ids=keep_ids
            )
            stats = ingest_selected(session, selected, target, settings)
            stats["pool"] = len(pool)
            fields_line = f", областей в пуле {len(sizes)}"
    _record_run_stats(settings, "etl authors", time.monotonic() - started, client)
    typer.echo(
        f"Ingested {stats['total']} authors "
        f"({stats['candidates']} supervisor candidates){fields_line} "
        f"[network={client.n_network_requests}, cache_hits={client.n_cache_hits}]"
    )


@etl_app.command("works")
def etl_works(
    since_years: Annotated[int | None, typer.Option(help="Recency window in years")] = None,
    per_author: Annotated[int | None, typer.Option(help="Max works stored per author")] = None,
    institution: Annotated[
        str | None, typer.Option(help="Только кандидаты этого вуза (по умолчанию — все)")
    ] = None,
    only_missing: Annotated[
        bool,
        typer.Option(
            "--only-missing/--all",
            help="Пропустить авторов, у которых работы уже загружены (экономит квоту)",
        ),
    ] = False,
    refresh: Annotated[bool, typer.Option("--refresh", help="Bypass the raw cache")] = False,
) -> None:
    """Ingest works (recent + most cited) for supervisor candidates.

    ``--institution`` разбивает многочасовой прогон SFR-5 на вузы: сбой стоит
    одного вуза, а не всего каталога.
    """
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    client = _make_client(settings, refresh)
    engine = make_engine(settings.sfr_db_url)

    started = time.monotonic()
    with session_scope(engine) as session:
        institution_db_id = None
        if institution is not None:
            institutions = list(session.execute(select(Institution)).scalars())
            institution_db_id = _select_institution(institutions, institution).id
        totals = ingest_works(
            session,
            client,
            since_years=since_years if since_years is not None else settings.works_since_years,
            per_author=per_author if per_author is not None else settings.works_per_author,
            institution_db_id=institution_db_id,
            only_missing=only_missing,
        )
    _record_run_stats(settings, "etl works", time.monotonic() - started, client)
    typer.echo(
        f"Ingested {totals['works']} works for {totals['authors']} candidates "
        f"({totals['with_abstract']} with abstract) "
        f"[network={client.n_network_requests}, cache_hits={client.n_cache_hits}]"
    )


@etl_app.command("backfill-mega")
def etl_backfill_mega() -> None:
    """Разнести счётчик организаций-соавторов по одинаковым работам (без сети)."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    engine = make_engine(settings.sfr_db_url)
    with session_scope(engine) as session:
        stats = backfill_institutions_distinct_count(session)
    typer.echo(f"Заполнено {stats['filled']} строк по {stats['known_works']} известным работам")


@etl_app.command("dedup")
def etl_dedup(
    apply: Annotated[
        bool, typer.Option("--apply/--dry-run", help="Записать склейки в БД или только показать")
    ] = False,
    review_out: Annotated[
        Path, typer.Option(help="Куда положить выборку на ручную проверку")
    ] = Path("packages/sfr-match/eval/dedup_for_review.md"),
    examples: Annotated[int, typer.Option(help="Сколько примеров каждого вида в файл")] = 10,
    decisions: Annotated[
        Path, typer.Option(help="Файл решений человека о склейках (§4 SPEC_SFR5c)")
    ] = DEFAULT_DECISIONS_PATH,
    orcid_names: Annotated[
        bool,
        typer.Option(
            "--orcid-names/--no-orcid-names",
            help="Проверять имя в записи ORCID у пар «разные ORCID» (pub.orcid.org, "
            "кэш в data/raw; #118). По умолчанию — выключено, сети нет",
        ),
    ] = False,
) -> None:
    """Склеить расщеплённые профили и отметить подозрительные (SPEC_SFR5 §3).

    Склейка необратима в пределах БД (работы переезжают на канонического автора),
    поэтому по умолчанию — `--dry-run` (#10); запись — только с явным `--apply`.
    Цели Makefile `catalog-*` передают `--apply` сами.

    Решения человека о склейках читаются из ``--decisions``: ``different``
    запрещает пару навсегда, ``same`` склеивает поверх блокеров. Путь по
    умолчанию отсчитывается от корня репозитория. Файла нет: при ``--apply`` —
    остановка с ошибкой (склейка необратима, а запреты человека не прочитаны),
    при ``--dry-run`` — предупреждение в stderr и работа по одним правилам.
    """
    # Проверка — до миграций и до открытия БД: остановиться нужно раньше, чем
    # прогон успел что-то сделать (ревью SFR-5c).
    try:
        human_decisions = load_decisions_or_fail(decisions, apply=apply)
    except DecisionsFileMissing as exc:
        typer.secho(f"ОШИБКА: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    if not decisions.exists():
        typer.secho(
            f"ВНИМАНИЕ: {decisions} не найден — решения человека о склейках не учтены; "
            "пары, уже разобранные руками, снова попадут в review",
            fg=typer.colors.YELLOW,
            err=True,
        )
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    engine = make_engine(settings.sfr_db_url)
    started = time.monotonic()
    orcid_client = OrcidClient(cache_dir=settings.raw_cache_dir) if orcid_names else None
    with session_scope(engine) as session:
        findings = find_splits(
            session,
            decisions=human_decisions,
            foreign_orcid=foreign_orcid_note(orcid_client) if orcid_client else None,
        )
        merges, namesakes = findings.merges, findings.namesakes
        merge_stats = {"groups": 0, "duplicates": 0, "works_moved": 0, "works_dropped": 0}
        aggregate_stats = {"canonical": 0, "changed": 0}
        if apply:
            merge_stats = apply_merges(session, merges)
            # Отдельный проход, а не часть apply_merges: тот пропускает уже
            # склеенных, а агрегаты нужно восстанавливать и после повторного
            # ингеста авторов, который их перезаписывает.
            aggregate_stats = recompute_merged_aggregates(session)
            suspect_stats = detect_suspect_merges(session)
            suspects = suspect_examples(session, limit=max(examples, 20))
        else:
            # Флаги suspect_merge не пересчитываются без --apply, но уже лежат в БД
            # с прошлого прогона — показываем их, а не «0 из 0».
            suspect_stats = {
                "checked": 0,
                "suspect": session.execute(
                    select(func.count()).select_from(Author).where(Author.suspect_merge.is_(True))
                ).scalar_one(),
            }
            suspects = suspect_examples(session, limit=max(examples, 20))
        review_out.parent.mkdir(parents=True, exist_ok=True)
        review_out.write_text(
            render_dedup_review(
                merges,
                namesakes,
                suspects,
                n_suspects=suspect_stats["suspect"],
                n_examples=examples,
                review=findings.review,
                near_duplicates=findings.near_duplicates,
                decisions=findings.decisions,
                initials_prefix=findings.initials_prefix,
            ),
            encoding="utf-8",
        )
        violations = findings.forbidden_but_merged
        ignored = sum(1 for o in findings.decisions if o.status == STATUS_NOT_IN_CATALOGUE)
    _record_run_stats(settings, "etl dedup", time.monotonic() - started)
    # Инвариант печатается до сводки: непустой список значит «не та БД», и это
    # надо увидеть, а не выискивать в строке со счётчиками (§4.2 SPEC_SFR5c).
    for outcome in violations:
        typer.secho(
            f"  ✗ {STATUS_FORBIDDEN_BUT_MERGED}: {outcome.decision.pair} "
            f"({outcome.decision.source}) — расклеить `sfr etl unmerge`",
            fg=typer.colors.RED,
            err=True,
        )
    typer.echo(
        f"{'Склеено' if apply else 'Склеек (dry-run, БД не тронута)'}: {len(merges)} "
        f"(дублей {merge_stats['duplicates']}, "
        f"работ перенесено {merge_stats['works_moved']}, дублей работ снято "
        f"{merge_stats['works_dropped']}); требуют решения человека: {len(findings.review)}; "
        f"похоже, один человек: {len(findings.near_duplicates)}; "
        f"инициалы-префикс: {len(findings.initials_prefix)}; "
        f"тёзок без сигнала: {len(namesakes)}; "
        f"подозрительных профилей: {suspect_stats['suspect']}"
        + (f" из {suspect_stats['checked']}" if apply else " (флаги прошлого --apply)")
        + "; "
        f"агрегатов пересчитано: {aggregate_stats['changed']} из {aggregate_stats['canonical']}; "
        f"решений человека: {len(findings.decisions)} (не в каталоге {ignored}, "
        f"запрещено-но-склеено {len(violations)}) "
        f"→ {review_out}"
    )
    if orcid_client is not None:
        typer.echo(
            f"ORCID: запросов к pub.orcid.org {orcid_client.n_requests}, "
            f"из кэша {orcid_client.n_cache_hits}"
        )


@etl_app.command("unmerge")
def etl_unmerge(
    author_ids: Annotated[
        list[str], typer.Argument(help="OpenAlex-id дублей, которых расклеить (A5…)")
    ],
    apply: Annotated[
        bool, typer.Option("--apply/--dry-run", help="Записать в БД или только показать план")
    ] = False,
) -> None:
    """Развести ошибочно склеенный дубль и канонического автора (#108).

    Работы обоих восстанавливаются из дискового кэша OpenAlex (сеть — только
    если работ дубля в кэше нет), счётчики и темы — из ``raw``. Профили обоих
    удаляются: после — ``sfr etl build-profiles``. По умолчанию ``--dry-run``.
    """
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    client = _make_client(settings, refresh=False)
    engine = make_engine(settings.sfr_db_url)
    started = time.monotonic()
    failed = False
    with session_scope(engine) as session:
        for author_id in author_ids:
            try:
                stats = unmerge_author(session, client, author_id, settings, dry_run=not apply)
            except UnmergeError as exc:
                typer.secho(f"  ✗ {exc}", fg=typer.colors.RED, err=True)
                failed = True
                continue
            if stats["status"] == "not_merged":
                typer.echo(f"  – {author_id}: не склеен, нечего делать")
                continue
            works = stats.get("works_after")
            typer.echo(
                f"  {'✓' if apply else '·'} {author_id} ← {stats['canonical']}: "
                f"работ у канонического было {stats['works_on_canonical_before']}, "
                f"works_count по OpenAlex {stats['raw_works_count']}"
                + (f", восстановлено работ {works}" if works else " (dry-run)")
            )
    _record_run_stats(settings, "etl unmerge", time.monotonic() - started, client)
    typer.echo(
        f"{'Применено' if apply else 'План (dry-run, БД не тронута)'} "
        f"[network={client.n_network_requests}, cache_hits={client.n_cache_hits}]"
        + ("; после --apply запусти `sfr etl build-profiles`" if apply else "")
    )
    # Расклейка руками — это решение человека; без строки в файле решений те же
    # правила склеят пару обратно при следующей пересборке каталога (§4.1).
    if not failed:
        typer.echo(f"Внести вердикт в {DEFAULT_DECISIONS_PATH} строкой (правит человек, не агент):")
        for author_id in author_ids:
            typer.echo(
                f'  {{"ids": ["<канонический>", "{author_id}"], "verdict": "different", '
                f'"by": "<кто>", "date": "<ГГГГ-ММ-ДД>", "source": "<#issue>", "note": "<почему>"}}'
            )
    if failed:
        raise typer.Exit(code=1)


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
        n_lines = export_profiles_jsonl(session, out, settings)
    _record_run_stats(settings, "export jsonl", time.monotonic() - started)
    typer.echo(f"Exported {n_lines} profiles to {out}")


@export_app.command("cards")
def export_cards(
    out: Annotated[Path, typer.Option(help="Output JSONL path")] = Path(
        "data/exports/cards_sfr5c.jsonl"
    ),
) -> None:
    """Export card enrichment for the API (SFR-3): citations + top works per supervisor."""
    settings = _load_settings()
    upgrade_to_head(settings.sfr_db_url)
    engine = make_engine(settings.sfr_db_url)
    started = time.monotonic()
    with session_scope(engine) as session:
        n_lines = export_cards_jsonl(session, out, settings)
    _record_run_stats(settings, "export cards", time.monotonic() - started)
    typer.echo(f"Exported {n_lines} cards to {out}")


@app.command("report")
def report(
    out: Annotated[Path, typer.Option(help="Output Markdown path")] = Path(
        "docs/reports/REPORT.md"
    ),
) -> None:
    """Generate the run report (docs/reports/REPORT.md)."""
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
