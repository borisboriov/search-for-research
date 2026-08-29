"""What exactly goes into the index: the SFR-2 composition experiment (SPEC_SFR2 §5).

SFR-1 left a hypothesis: mpnet sees only the first 128 tokens — name, the topics
line and the beginning of the first work — and still takes 21 of 22 in-domain
queries. If that is where the signal lives, the abstract fragments that most of
SFR-0 went into may not be paying for themselves.

Three ways to build the *indexed* text of the same profile:

``full``            the ``profile_text`` from SFR-0 (baseline);
``topics``          header + the key-topics line only;
``topics_titles``   the same plus work titles, without abstract fragments.

Only the indexed text changes; the card shown to a user is always the full
profile (see ``ProfileRecord.display_text``).
"""

from typing import Literal, get_args

from sfr_core.profile import MAX_TOPICS, WorkForProfile, select_works_for_profile
from sfr_core.schemas import ProfileExport

Composition = Literal["full", "topics", "topics_titles"]
COMPOSITIONS: tuple[Composition, ...] = get_args(Composition)

MAX_TITLE_CHARS = 200
MAX_CHARS = 1500  # same ceiling as build_profile_text, so variants stay comparable


def _header(export: ProfileExport) -> str:
    """The first line of profile_text, rebuilt from the same fields (sfr_core.profile)."""
    header = (
        f"{export.name}."
        if export.institution is None
        else f"{export.name} — {export.institution}."
    )
    if export.h_index is not None:
        header += f" h-index: {export.h_index}."
    return header


def _titles(export: ProfileExport) -> list[str]:
    """Titles of the works the full profile_text would have quoted, same selection."""
    works = [
        WorkForProfile(
            title=work.title,
            publication_year=work.publication_year,
            cited_by_count=work.cited_by_count,
            abstract_text=None,
        )
        for work in export.works
    ]
    entries = []
    for work in select_works_for_profile(works):
        title = " ".join(work.title.split())[:MAX_TITLE_CHARS]
        year = f" ({work.publication_year})" if work.publication_year else ""
        entries.append(f"«{title}»{year}.")
    return entries


def compose_indexed_text(export: ProfileExport, mode: Composition = "full") -> str:
    """Build the text that will be embedded for this profile."""
    if mode == "full":
        return export.profile_text
    parts = [_header(export)]
    if export.topics:
        parts.append("Ключевые темы: " + "; ".join(export.topics[:MAX_TOPICS]) + ".")
    if mode == "topics_titles":
        for entry in _titles(export):
            if len("\n".join([*parts, entry])) > MAX_CHARS:
                break
            parts.append(entry)
    return "\n".join(parts)
