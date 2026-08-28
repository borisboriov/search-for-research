"""Works ingest for supervisor candidates: recent + most-cited, abstract reconstruction."""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from sfr_core.models import Author, Work
from sfr_etl.abstracts import reconstruct_abstract
from sfr_etl.client import OpenAlexClient
from sfr_etl.ingest import short_id

log = structlog.get_logger(__name__)

# Trim the payload: only the fields the pipeline relies on (verified against the live API).
WORK_SELECT_FIELDS = (
    "id,display_name,publication_year,cited_by_count,language,topics,abstract_inverted_index"
)


def merge_work_records(
    cited: list[dict[str, Any]],
    recent: list[dict[str, Any]],
    per_author: int,
) -> list[dict[str, Any]]:
    """Combine most-cited and most-recent works, dedupe by id, cap at ``per_author``.

    Half the budget (rounded up) goes to the most-cited works, the rest is filled
    with the freshest ones — a profile needs both signals (SPEC §4).
    """
    merged: dict[str, dict[str, Any]] = {}
    cited_budget = (per_author + 1) // 2
    for record in cited[:cited_budget]:
        merged[record["id"]] = record
    for record in recent:
        if len(merged) >= per_author:
            break
        merged.setdefault(record["id"], record)
    # top up with remaining cited works if recent ones were not enough
    for record in cited[cited_budget:]:
        if len(merged) >= per_author:
            break
        merged.setdefault(record["id"], record)
    return list(merged.values())


def upsert_work(
    session: Session,
    record: dict[str, Any],
    author_db_id: int,
    *,
    since_year: int,
) -> Work | None:
    title = record.get("display_name") or record.get("title")
    if not title:
        return None  # a work without any title is useless for profile text
    openalex_id = short_id(record["id"])
    work = session.execute(
        select(Work).where(Work.openalex_id == openalex_id, Work.author_id == author_db_id)
    ).scalar_one_or_none()
    if work is None:
        work = Work(openalex_id=openalex_id, author_id=author_db_id)
        session.add(work)
    work.title = title
    work.publication_year = record.get("publication_year")
    work.abstract_text = reconstruct_abstract(record.get("abstract_inverted_index"))
    work.topics = [
        {"display_name": t.get("display_name"), "score": t.get("score")}
        for t in record.get("topics") or []
    ]
    work.cited_by_count = record.get("cited_by_count") or 0
    work.language = record.get("language")
    work.is_recent = work.publication_year is not None and work.publication_year >= since_year
    return work


def ingest_works_for_author(
    session: Session,
    client: OpenAlexClient,
    author: Author,
    *,
    since_years: int,
    per_author: int,
    current_year: int | None = None,
) -> dict[str, int]:
    """Fetch recent + most-cited works of one author and upsert them."""
    year = current_year or datetime.now(UTC).year
    since_year = year - since_years + 1
    author_filter = f"authorships.author.id:{author.openalex_id}"

    cited_body = client.get(
        "/works",
        {
            "filter": author_filter,
            "sort": "cited_by_count:desc",
            "per-page": per_author,
            "select": WORK_SELECT_FIELDS,
        },
    )
    recent_body = client.get(
        "/works",
        {
            "filter": f"{author_filter},publication_year:>{since_year - 1}",
            "sort": "publication_date:desc",
            "per-page": per_author,
            "select": WORK_SELECT_FIELDS,
        },
    )
    records = merge_work_records(
        cited_body.get("results", []), recent_body.get("results", []), per_author
    )
    n_saved = 0
    n_abstracts = 0
    for record in records:
        work = upsert_work(session, record, author.id, since_year=since_year)
        if work is not None:
            n_saved += 1
            if work.abstract_text:
                n_abstracts += 1
    return {"saved": n_saved, "with_abstract": n_abstracts}


def ingest_works(
    session: Session,
    client: OpenAlexClient,
    *,
    since_years: int,
    per_author: int,
) -> dict[str, int]:
    """Ingest works for all supervisor candidates."""
    candidates = list(
        session.execute(select(Author).where(Author.is_supervisor_candidate.is_(True))).scalars()
    )
    totals = {"authors": 0, "works": 0, "with_abstract": 0}
    for author in candidates:
        stats = ingest_works_for_author(
            session, client, author, since_years=since_years, per_author=per_author
        )
        totals["authors"] += 1
        totals["works"] += stats["saved"]
        totals["with_abstract"] += stats["with_abstract"]
        if totals["authors"] % 25 == 0:
            log.info("works_progress", **totals)
    log.info("works_ingested", **totals)
    return totals
