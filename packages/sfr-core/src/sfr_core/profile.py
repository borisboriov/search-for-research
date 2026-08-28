"""profile_text builder — the main SFR-0 artefact (input for future embeddings).

Pure logic: takes plain values, returns text. Source language is preserved
(no translation), per SPEC §3.
"""

from dataclasses import dataclass

FRAGMENT_CHARS = 220
MAX_TOPICS = 7
MAX_WORKS = 10
MIN_WORKS_PREFERRED = 5


@dataclass(frozen=True)
class WorkForProfile:
    title: str
    publication_year: int | None
    cited_by_count: int
    abstract_text: str | None


def _truncate_at_word(text: str, limit: int) -> str:
    text = " ".join(text.split())  # collapse whitespace/newlines
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def select_works_for_profile(
    works: list[WorkForProfile], max_works: int = MAX_WORKS
) -> list[WorkForProfile]:
    """Most-cited first (up to half the slots), then the freshest — dedupe, cap."""
    by_citations = sorted(works, key=lambda w: w.cited_by_count, reverse=True)
    by_year = sorted(works, key=lambda w: w.publication_year or 0, reverse=True)
    selected: list[WorkForProfile] = []
    for work in by_citations[: (max_works + 1) // 2]:
        if work not in selected:
            selected.append(work)
    for work in by_year:
        if len(selected) >= max_works:
            break
        if work not in selected:
            selected.append(work)
    return selected


def build_profile_text(
    *,
    name: str,
    institution_name: str | None,
    topics: list[str],
    works: list[WorkForProfile],
    h_index: int | None = None,
    min_chars: int = 300,
    max_chars: int = 1500,
) -> str:
    """Assemble a coherent 300–1500 char profile: name, affiliation, topics, works.

    The lower bound is best-effort: with no works and no topics there is simply
    nothing to say — completeness is tracked by the caller.
    """
    parts: list[str] = []
    header = f"{name}." if institution_name is None else f"{name} — {institution_name}."
    if h_index is not None:
        header += f" h-index: {h_index}."
    parts.append(header)

    if topics:
        parts.append("Ключевые темы: " + "; ".join(topics[:MAX_TOPICS]) + ".")

    selected = select_works_for_profile(works)
    for work in selected:
        year = f" ({work.publication_year})" if work.publication_year else ""
        entry = f"«{_truncate_at_word(work.title, 200)}»{year}."
        if work.abstract_text:
            entry += " " + _truncate_at_word(work.abstract_text, FRAGMENT_CHARS)
        candidate = "\n".join([*parts, entry])
        if len(candidate) > max_chars:
            break
        parts.append(entry)

    text = "\n".join(parts)

    # Too short but there is unused abstract text — extend the first abstracts.
    if len(text) < min_chars:
        for work in selected:
            if work.abstract_text and len(work.abstract_text) > FRAGMENT_CHARS:
                extended = _truncate_at_word(
                    work.abstract_text, FRAGMENT_CHARS + (min_chars - len(text)) + 100
                )
                short = _truncate_at_word(work.abstract_text, FRAGMENT_CHARS)
                text = text.replace(short, extended, 1)
            if len(text) >= min_chars:
                break

    return text[:max_chars]
