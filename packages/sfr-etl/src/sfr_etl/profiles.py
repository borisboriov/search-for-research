"""Build SupervisorProfile rows (profile_text + completeness) for candidates."""

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sfr_core.models import Author, SupervisorProfile
from sfr_core.profile import WorkForProfile, build_profile_text
from sfr_core.settings import Settings

log = structlog.get_logger(__name__)


def candidate_authors(session: Session) -> list[Author]:
    return list(
        session.execute(
            select(Author)
            .where(Author.is_supervisor_candidate.is_(True))
            .options(
                selectinload(Author.works),
                selectinload(Author.topics),
                selectinload(Author.institution),
            )
        ).scalars()
    )


def build_profiles(session: Session, settings: Settings) -> dict[str, int]:
    """(Re)build a SupervisorProfile for every candidate. Idempotent by author_id."""
    stats = {"profiles": 0, "in_range": 0, "without_works": 0}
    for author in candidate_authors(session):
        topics = [t.topic_name for t in sorted(author.topics, key=lambda t: -t.score)]
        works = [
            WorkForProfile(
                title=w.title,
                publication_year=w.publication_year,
                cited_by_count=w.cited_by_count,
                abstract_text=w.abstract_text,
            )
            for w in author.works
        ]
        institution_name = None
        if author.institution is not None:
            institution_name = author.institution.name_ru or author.institution.name_en

        text = build_profile_text(
            name=author.display_name,
            institution_name=institution_name,
            topics=topics,
            works=works,
            h_index=author.h_index,
            min_chars=settings.profile_text_min_chars,
            max_chars=settings.profile_text_max_chars,
        )

        profile = session.execute(
            select(SupervisorProfile).where(SupervisorProfile.author_id == author.id)
        ).scalar_one_or_none()
        if profile is None:
            profile = SupervisorProfile(author_id=author.id)
            session.add(profile)
        profile.institution_id = author.last_known_institution_id
        profile.profile_text = text
        profile.n_works = len(author.works)
        profile.n_abstracts = sum(1 for w in author.works if w.abstract_text)

        stats["profiles"] += 1
        if settings.profile_text_min_chars <= len(text) <= settings.profile_text_max_chars:
            stats["in_range"] += 1
        if not author.works:
            stats["without_works"] += 1
    log.info("profiles_built", **stats)
    return stats
