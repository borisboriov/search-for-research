"""JSONL export of supervisor profiles — the input for SFR-1 (embeddings)."""

from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sfr_core.models import Author, SupervisorProfile
from sfr_core.schemas import ProfileExport, WorkExport

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
