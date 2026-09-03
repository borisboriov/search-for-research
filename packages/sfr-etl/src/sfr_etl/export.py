"""JSONL export of supervisor profiles — the input for SFR-1 (embeddings)."""

from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sfr_core.models import Author, SupervisorProfile
from sfr_core.profile import WorkForProfile, select_works_for_profile
from sfr_core.schemas import CardExport, ProfileExport, TopWorkCard, WorkExport

log = structlog.get_logger(__name__)

MAX_EXPORT_TOPICS = 10


def export_profiles_jsonl(session: Session, out_path: Path) -> int:
    """Write one JSON line per supervisor profile. Returns the number of lines."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profiles = list(
        session.execute(
            select(SupervisorProfile)
            .join(Author, SupervisorProfile.author_id == Author.id)
            .options(
                selectinload(SupervisorProfile.author).selectinload(Author.works),
                selectinload(SupervisorProfile.author).selectinload(Author.topics),
                selectinload(SupervisorProfile.author).selectinload(Author.institution),
            )
            .order_by(Author.openalex_id)
        ).scalars()
    )
    n_lines = 0
    with out_path.open("w", encoding="utf-8") as f:
        for profile in profiles:
            author = profile.author
            topics = [t.topic_name for t in sorted(author.topics, key=lambda t: -t.score)]
            record = ProfileExport(
                id=author.openalex_id,
                name=author.display_name,
                institution=(
                    author.institution.name_ru or author.institution.name_en
                    if author.institution
                    else None
                ),
                h_index=author.h_index,
                works_count=author.works_count,
                topics=topics[:MAX_EXPORT_TOPICS],
                profile_text=profile.profile_text,
                works=[
                    WorkExport(
                        openalex_id=w.openalex_id,
                        title=w.title,
                        publication_year=w.publication_year,
                        cited_by_count=w.cited_by_count,
                        has_abstract=bool(w.abstract_text),
                    )
                    for w in sorted(author.works, key=lambda w: -(w.publication_year or 0))
                ],
            )
            f.write(record.model_dump_json() + "\n")
            n_lines += 1
    log.info("profiles_exported", lines=n_lines, path=str(out_path))
    return n_lines


def export_cards_jsonl(session: Session, out_path: Path) -> int:
    """Card enrichment for the API (SFR-3): author citations + 10 top works.

    Works are picked by the same most-cited-then-freshest heuristic as
    ``profile_text`` (``select_works_for_profile``), so the person reads the same
    publications the model indexed. ``position``/``email`` stay ``None``: there is
    no such data in the catalogue and nothing new is parsed (SPEC_SFR3 §4).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profiles = list(
        session.execute(
            select(SupervisorProfile)
            .join(Author, SupervisorProfile.author_id == Author.id)
            .options(selectinload(SupervisorProfile.author).selectinload(Author.works))
            .order_by(Author.openalex_id)
        ).scalars()
    )
    n_lines = 0
    with out_path.open("w", encoding="utf-8") as f:
        for profile in profiles:
            author = profile.author
            selected = select_works_for_profile(
                [
                    WorkForProfile(
                        title=w.title,
                        publication_year=w.publication_year,
                        cited_by_count=w.cited_by_count,
                        abstract_text=None,
                    )
                    for w in author.works
                ]
            )
            record = CardExport(
                id=author.openalex_id,
                cited_by_count=author.cited_by_count,
                top_works=[TopWorkCard(title=w.title, year=w.publication_year) for w in selected],
            )
            f.write(record.model_dump_json() + "\n")
            n_lines += 1
    log.info("cards_exported", lines=n_lines, path=str(out_path))
    return n_lines
