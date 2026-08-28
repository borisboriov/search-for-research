"""Ingest: OpenAlex records → DB (institutions, authors). Idempotent upserts by openalex_id."""

import re
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from sfr_core.heuristics import is_supervisor_candidate
from sfr_core.models import Author, AuthorTopic, Institution
from sfr_core.settings import Settings
from sfr_etl.client import OpenAlexClient

log = structlog.get_logger(__name__)

_CYRILLIC_RE = re.compile("[а-яА-ЯёЁ]")


def short_id(openalex_url: str) -> str:
    """'https://openalex.org/A123' → 'A123' (already-short IDs pass through)."""
    return openalex_url.rsplit("/", 1)[-1]


def extract_cyrillic_name(alternatives: list[str]) -> str | None:
    """OpenAlex has no name_ru field; take the first Cyrillic display_name_alternative."""
    for name in alternatives:
        if _CYRILLIC_RE.search(name):
            return name
    return None


def last_publication_year(counts_by_year: list[dict[str, Any]]) -> int | None:
    """Latest year with works_count > 0. Element order is not guaranteed by the API."""
    years = [c["year"] for c in counts_by_year if c.get("works_count", 0) > 0]
    return max(years) if years else None


def upsert_institution(session: Session, record: dict[str, Any]) -> Institution:
    openalex_id = short_id(record["id"])
    institution = session.execute(
        select(Institution).where(Institution.openalex_id == openalex_id)
    ).scalar_one_or_none()
    if institution is None:
        institution = Institution(openalex_id=openalex_id)
        session.add(institution)
    institution.ror_id = record.get("ror")
    institution.name_en = record["display_name"]
    institution.name_ru = extract_cyrillic_name(record.get("display_name_alternatives") or [])
    institution.country = record.get("country_code")
    session.flush()
    return institution


def upsert_author(
    session: Session,
    record: dict[str, Any],
    institution_db_id: int,
    settings: Settings,
    *,
    current_year: int | None = None,
) -> Author:
    openalex_id = short_id(record["id"])
    author = session.execute(
        select(Author).where(Author.openalex_id == openalex_id)
    ).scalar_one_or_none()
    if author is None:
        author = Author(openalex_id=openalex_id)
        session.add(author)

    summary_stats = record.get("summary_stats") or {}
    author.orcid = record.get("orcid")
    author.display_name = record["display_name"]
    author.last_known_institution_id = institution_db_id
    author.works_count = record.get("works_count") or 0
    author.cited_by_count = record.get("cited_by_count") or 0
    author.h_index = summary_stats.get("h_index")
    author.i10_index = summary_stats.get("i10_index")
    author.fetched_at = datetime.now(UTC).replace(tzinfo=None)
    author.raw = record

    year = current_year or datetime.now(UTC).year
    author.is_supervisor_candidate = is_supervisor_candidate(
        works_count=author.works_count,
        h_index=author.h_index,
        last_publication_year=last_publication_year(record.get("counts_by_year") or []),
        current_year=year,
        min_works=settings.supervisor_min_works,
        min_h_index=settings.supervisor_min_h_index,
        recent_years=settings.supervisor_recent_years,
    )
    session.flush()

    # Replace author topics (idempotent re-ingest). Score = `count` from the author's
    # `topics` list; x_concepts are deprecated by OpenAlex and not used.
    session.execute(delete(AuthorTopic).where(AuthorTopic.author_id == author.id))
    for topic in record.get("topics") or []:
        session.add(
            AuthorTopic(
                author_id=author.id,
                topic_name=topic["display_name"],
                score=float(topic.get("count") or 0),
            )
        )
    return author


def ingest_authors(
    session: Session,
    client: OpenAlexClient,
    institution: Institution,
    settings: Settings,
    *,
    max_authors: int,
) -> dict[str, int]:
    """Fetch authors affiliated with the institution, sorted by works_count desc."""
    n_total = 0
    n_candidates = 0
    for record in client.paginate(
        "/authors",
        {
            "filter": f"last_known_institutions.id:{institution.openalex_id}",
            "sort": "works_count:desc",
        },
        max_records=max_authors,
    ):
        author = upsert_author(session, record, institution.id, settings)
        n_total += 1
        if author.is_supervisor_candidate:
            n_candidates += 1
    log.info("authors_ingested", total=n_total, candidates=n_candidates)
    return {"total": n_total, "candidates": n_candidates}
