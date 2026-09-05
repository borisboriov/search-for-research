"""profile_text builder — the main SFR-0 artefact (input for future embeddings).

Pure logic: takes plain values, returns text. Source language is preserved
(no translation), per SPEC §3.
"""

from dataclasses import dataclass

FRAGMENT_CHARS = 220
MAX_TOPICS = 7
MAX_WORKS = 10
# Профиль без загруженных работ: единственный источник смысла — темы автора,
# поэтому их берётся больше. Появилось в SFR-5, когда часть каталога осталась
# без работ (дневной бюджет OpenAlex, см. docs/DECISIONS.md).
MAX_TOPICS_NO_WORKS = 20


@dataclass(frozen=True)
class WorkForProfile:
    title: str
    publication_year: int | None
    cited_by_count: int
    abstract_text: str | None
    # SFR-5: работа мегаколлаборации (сотни организаций-соавторов). Такие работы
    # цитируются на порядки чаще личных и, попав в profile_text, делают профиль
    # физика ATLAS неотличимым от профиля любого другого участника эксперимента.
    is_mega_collaboration: bool = False


def _truncate_at_word(text: str, limit: int) -> str:
    text = " ".join(text.split())  # collapse whitespace/newlines
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _select(works: list[WorkForProfile], max_works: int) -> list[WorkForProfile]:
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


def select_works_for_profile(
    works: list[WorkForProfile], max_works: int = MAX_WORKS
) -> list[WorkForProfile]:
    """Works for the profile text, mega-collaboration papers deprioritised (SFR-5).

    Собственные работы автора выбираются первыми; работы мегаколлабораций
    добираются только в оставшиеся слоты. Для физика, у которого других работ
    нет, профиль не пустеет — он просто состоит из них.
    """
    regular = [w for w in works if not w.is_mega_collaboration]
    selected = _select(regular, max_works)
    if len(selected) < max_works:
        mega = [w for w in works if w.is_mega_collaboration]
        for work in _select(mega, max_works - len(selected)):
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

    topics_cap = MAX_TOPICS if works else MAX_TOPICS_NO_WORKS
    if topics:
        parts.append("Ключевые темы: " + "; ".join(topics[:topics_cap]) + ".")

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

    if len(text) > max_chars:
        # The extension pass can overshoot: cut back at a whitespace boundary, not mid-word.
        cut = text[:max_chars]
        boundary = max(cut.rfind(" "), cut.rfind("\n"))
        text = cut[:boundary] + "…" if boundary > 0 else cut
    return text
