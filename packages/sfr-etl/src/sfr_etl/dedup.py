"""Дедупликация авторов каталога (SPEC_SFR5 §3) — долг, тянущийся с SFR-0.

Две разные задачи, которые легко перепутать:

**Расщеплённый профиль** — один человек существует в OpenAlex несколькими
author-сущностями («В. В. Иванов» ×3, «T. Aushev» с 984 и 85 работами). Это
чинится склейкой, и цена ошибки высока: склеить двух тёзок хуже, чем оставить
дубль. Поэтому склеиваем только по сигналам, которые про личность, а не про
похожесть:

* ``orcid`` — идентификатор человека; совпал — это один человек;
* одинаковое имя + один вуз + **общая работа**: одна и та же публикация,
  записанная на обе сущности, — след того, что дизамбигуация OpenAlex
  разошлась на одном и том же авторе.

Пары «одинаковое имя + один вуз» без третьего сигнала не склеиваются: это ровно
тот случай, где живут тёзки. Они выписываются в отчёт как кандидаты на ручной
разбор — знать о них полезно, автоматически трогать нельзя.

**Чужая склейка** — обратная беда: OpenAlex положил в один профиль работы двух
людей (NLP-специалист с «Т-клетками мышей», химик с нейтринным экспериментом).
Расклеивать автоматически нечем — работы придётся делить между людьми, которых
мы не знаем. Здесь только детектор: работы профиля кластеризуются по общим
подобластям, и если две крупные группы не имеют ни одной общей подобласти,
профиль получает флаг ``suspect_merge``. Биофизик такой детектор не ловит:
его работы связаны цепочкой общих подобластей, а не разорваны надвое.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sfr_core.models import Author, AuthorTopic, SupervisorProfile, Work

log = structlog.get_logger(__name__)

# Доля работ, ниже которой тематическая группа считается шумом, а не «вторым
# человеком» в склеенном профиле.
SUSPECT_MIN_SHARE = 0.25
# Меньше этого числа работ — судить о бимодальности не по чему.
SUSPECT_MIN_WORKS = 8

_INITIALS_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def normalize_orcid(value: str | None) -> str | None:
    """``https://orcid.org/0000-0002-...`` → ``0000-0002-...``; пустое → None."""
    if not value:
        return None
    tail = value.strip().rstrip("/").rsplit("/", 1)[-1].upper()
    return tail or None


def name_key(display_name: str) -> str:
    """Ключ сравнения имён: фамилия + инициалы остальных частей, по порядку.

    «T. Aushev», «Timofey Aushev» и «Aushev T.» дают один ключ; «A. Ivanov» и
    «B. Ivanov» — разные, как и «A. M. Kondratenko» с «M. A. Kondratenko»
    (порядок инициалов различает людей — на живых данных это две разные
    сущности с общей работой, то есть соавторы, а не расщеплённый профиль).

    Фамилия — последняя часть длиннее одной буквы: OpenAlex пишет и «Фамилия И.»,
    и «Имя Фамилия». Брать самую длинную часть нельзя — «Alexander Karpov» тогда
    сводится к «alexander», и все Александры вуза становятся тёзками.
    """
    cleaned = _INITIALS_RE.sub(" ", display_name).lower()
    parts = [p for p in cleaned.split() if p]
    if not parts:
        return ""
    surname_at = next(
        (i for i in range(len(parts) - 1, -1, -1) if len(parts[i]) > 1), len(parts) - 1
    )
    initials = [p[0] for i, p in enumerate(parts) if i != surname_at]
    return parts[surname_at] + "|" + "".join(initials)


# Сколько тем из топ-5 должно совпасть, чтобы «И. Фамилия» и «Иван Фамилия»
# из одного вуза считались одним человеком.
ABBREV_TOPIC_OVERLAP = 3


def _spelled_out(display_name: str) -> bool:
    """Есть ли в имени развёрнутая часть, кроме фамилии («Ilya A. Ryzhikov» — да)."""
    cleaned = _INITIALS_RE.sub(" ", display_name).lower()
    parts = [p for p in cleaned.split() if p]
    if len(parts) < 2:
        return False
    surname_at = next(
        (i for i in range(len(parts) - 1, -1, -1) if len(parts[i]) > 1), len(parts) - 1
    )
    return any(len(p) > 1 for i, p in enumerate(parts) if i != surname_at)


def is_abbreviation_pair(left: Author, right: Author) -> bool:
    """Одно имя записано полностью, второе — инициалами, ключ имени тот же.

    «Dmitry D. Sokoloff» и «D. D. Sokoloff» — одна и та же запись в двух формах;
    два **по-разному** развёрнутых имени с одним ключом (два «А. Е. Романов»)
    сюда не попадают: различить их по имени нечем.
    """
    return _spelled_out(left.display_name) != _spelled_out(right.display_name)


@dataclass
class MergeGroup:
    """Один человек: канонический автор и его дубли."""

    canonical: str
    duplicates: list[str]
    signal: str
    names: list[str] = field(default_factory=list)
    institutions: list[str] = field(default_factory=list)


class _Union:
    def __init__(self, items: Iterable[int]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a

    def groups(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        for item in self.parent:
            out.setdefault(self.find(item), []).append(item)
        return out


def _catalogue_authors(session: Session) -> list[Author]:
    return list(
        session.execute(
            select(Author)
            .where(Author.is_supervisor_candidate.is_(True), Author.merged_into_id.is_(None))
            .options(selectinload(Author.institution))
        ).scalars()
    )


def applied_merges(session: Session) -> list[MergeGroup]:
    """Склейки, уже записанные в БД, — чтобы повторный прогон был идемпотентен.

    Без этого второй ``sfr etl dedup --apply`` отчитался бы «склеек 0»: дубли
    из каталога уже выбыли, и детектор их больше не видит.
    """
    groups: dict[int, MergeGroup] = {}
    rows = list(session.execute(select(Author).where(Author.merged_into_id.is_not(None))).scalars())
    for duplicate in rows:
        canonical = session.get(Author, duplicate.merged_into_id)
        if canonical is None:  # pragma: no cover — FK гарантирует наличие
            continue
        group = groups.get(canonical.id)
        if group is None:
            group = MergeGroup(
                canonical=canonical.openalex_id,
                duplicates=[],
                signal="склеено ранее",
                names=[canonical.display_name],
                institutions=[_institution_name(canonical)],
            )
            groups[canonical.id] = group
        group.duplicates.append(duplicate.openalex_id)
        group.names.append(duplicate.display_name)
        group.institutions.append(_institution_name(duplicate))
    return sorted(groups.values(), key=lambda g: g.canonical)


def find_splits(session: Session) -> tuple[list[MergeGroup], list[MergeGroup]]:
    """Группы для склейки и отдельно — тёзки без третьего сигнала (не склеивать).

    Возвращает ``(merges, namesakes)``; уже применённые склейки входят в первый
    список с сигналом «склеено ранее».
    """
    authors = _catalogue_authors(session)
    by_db_id = {a.id: a for a in authors}
    union = _Union(by_db_id)
    signals: dict[int, str] = {}

    by_orcid: dict[str, list[int]] = {}
    for author in authors:
        orcid = normalize_orcid(author.orcid)
        if orcid:
            by_orcid.setdefault(orcid, []).append(author.id)
    for ids in by_orcid.values():
        for other in ids[1:]:
            union.union(ids[0], other)
            signals[union.find(ids[0])] = "orcid"

    # Имя + вуз — только как рамка поиска; решает наличие общей работы.
    by_name: dict[tuple[str, int | None], list[int]] = {}
    for author in authors:
        key = name_key(author.display_name)
        if key:
            by_name.setdefault((key, author.last_known_institution_id), []).append(author.id)
    candidate_ids = {i for ids in by_name.values() if len(ids) > 1 for i in ids}

    shared: dict[int, set[str]] = {}
    if candidate_ids:
        rows = session.execute(
            select(Work.author_id, Work.openalex_id).where(Work.author_id.in_(candidate_ids))
        ).all()
        for author_id, work_id in rows:
            shared.setdefault(author_id, set()).add(work_id)

    top_topics: dict[int, set[str]] = {}
    if candidate_ids:
        for author_id in candidate_ids:
            top_topics[author_id] = set(
                session.execute(
                    select(AuthorTopic.topic_name)
                    .where(AuthorTopic.author_id == author_id)
                    .order_by(AuthorTopic.score.desc())
                    .limit(5)
                ).scalars()
            )

    for ids in by_name.values():
        if len(ids) < 2:
            continue
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                if shared.get(left, set()) & shared.get(right, set()):
                    union.union(left, right)
                    signals.setdefault(union.find(left), "name+institution+work")
                elif (
                    is_abbreviation_pair(by_db_id[left], by_db_id[right])
                    and len(top_topics.get(left, set()) & top_topics.get(right, set()))
                    >= ABBREV_TOPIC_OVERLAP
                ):
                    union.union(left, right)
                    signals.setdefault(union.find(left), "abbrev+institution+topics")

    # Тёзки: одно имя и один вуз, но ни одного сигнала о личности. Автоматически
    # не трогаем — только в отчёт, на глаза человеку.
    namesakes: list[MergeGroup] = []
    for ids in by_name.values():
        if len(ids) < 2 or len({union.find(i) for i in ids}) == 1:
            continue
        ordered = sorted(ids, key=lambda i: by_db_id[i].openalex_id)
        namesakes.append(
            MergeGroup(
                canonical=by_db_id[ordered[0]].openalex_id,
                duplicates=[by_db_id[i].openalex_id for i in ordered[1:]],
                signal="одно имя и вуз, общих работ и ORCID нет — не склеиваем",
                names=[by_db_id[i].display_name for i in ordered],
                institutions=[_institution_name(by_db_id[i]) for i in ordered],
            )
        )

    merges: list[MergeGroup] = []
    for root, members in union.groups().items():
        if len(members) < 2:
            continue
        ordered = sorted(
            members, key=lambda i: (-(by_db_id[i].works_count or 0), by_db_id[i].openalex_id)
        )
        merges.append(
            MergeGroup(
                canonical=by_db_id[ordered[0]].openalex_id,
                duplicates=[by_db_id[i].openalex_id for i in ordered[1:]],
                signal=signals.get(root, "orcid"),
                names=[by_db_id[i].display_name for i in ordered],
                institutions=[_institution_name(by_db_id[i]) for i in ordered],
            )
        )
    merges.sort(key=lambda g: g.canonical)
    namesakes.sort(key=lambda g: g.canonical)
    return applied_merges(session) + merges, namesakes


def _institution_name(author: Author) -> str:
    if author.institution is None:
        return "—"
    return author.institution.name_ru or author.institution.name_en


def apply_merges(session: Session, groups: Sequence[MergeGroup]) -> dict[str, int]:
    """Перевести работы, темы и счётчики дублей на канонического автора.

    Счётчики агрегируются: ``works_count`` и ``cited_by_count`` складываются
    (у расщеплённого профиля они и были поделены между сущностями), ``h_index``
    берётся максимальный — сложить его нельзя, а пересчитать не из чего.
    Исходные записи OpenAlex дублей остаются в ``authors.raw``.
    """
    stats = {"groups": 0, "duplicates": 0, "works_moved": 0, "works_dropped": 0}
    for group in groups:
        canonical = session.execute(
            select(Author).where(Author.openalex_id == group.canonical)
        ).scalar_one()
        canonical_works = {
            work_id
            for (work_id,) in session.execute(
                select(Work.openalex_id).where(Work.author_id == canonical.id)
            )
        }
        canonical_topics = {
            topic.topic_name: topic
            for topic in session.execute(
                select(AuthorTopic).where(AuthorTopic.author_id == canonical.id)
            ).scalars()
        }
        for duplicate_id in group.duplicates:
            duplicate = session.execute(
                select(Author).where(Author.openalex_id == duplicate_id)
            ).scalar_one()
            if duplicate.merged_into_id is not None:
                continue  # уже склеен предыдущим прогоном
            for work in session.execute(
                select(Work).where(Work.author_id == duplicate.id)
            ).scalars():
                if work.openalex_id in canonical_works:
                    session.delete(work)
                    stats["works_dropped"] += 1
                else:
                    work.author_id = canonical.id
                    canonical_works.add(work.openalex_id)
                    stats["works_moved"] += 1
            for topic in session.execute(
                select(AuthorTopic).where(AuthorTopic.author_id == duplicate.id)
            ).scalars():
                existing = canonical_topics.get(topic.topic_name)
                if existing is None:
                    topic.author_id = canonical.id
                    canonical_topics[topic.topic_name] = topic
                else:
                    existing.score += topic.score
                    session.delete(topic)
            profile = session.execute(
                select(SupervisorProfile).where(SupervisorProfile.author_id == duplicate.id)
            ).scalar_one_or_none()
            if profile is not None:
                session.delete(profile)

            canonical.works_count = (canonical.works_count or 0) + (duplicate.works_count or 0)
            canonical.cited_by_count = (canonical.cited_by_count or 0) + (
                duplicate.cited_by_count or 0
            )
            if duplicate.h_index is not None:
                canonical.h_index = max(canonical.h_index or 0, duplicate.h_index)
            canonical.orcid = canonical.orcid or duplicate.orcid
            duplicate.merged_into_id = canonical.id
            duplicate.is_supervisor_candidate = False
            stats["duplicates"] += 1
        stats["groups"] += 1
        session.flush()
    log.info("dedup_merged", **stats)
    return stats


def topic_subfields(session: Session) -> dict[str, str]:
    """Карта «тема → подобласть» из сырых записей авторов.

    Работы, загруженные до SFR-5, хранят только имя темы; подобласть у них взять
    неоткуда, а кластеризовать по самим темам бесполезно — их в OpenAlex тысячи,
    и любой профиль рассыпается в пыль одиночек. Зато та же вложенная структура
    есть в ``authors.raw``, и одной прогулкой по ней строится общий словарь.
    """
    mapping: dict[str, str] = {}
    for (raw,) in session.execute(select(Author.raw).where(Author.raw.is_not(None))):
        for topic in (raw or {}).get("topics") or []:
            name = topic.get("display_name")
            subfield = (topic.get("subfield") or {}).get("display_name")
            if name and subfield:
                mapping.setdefault(str(name), str(subfield))
    return mapping


def _work_subfields(work: Work, mapping: dict[str, str] | None = None) -> set[str]:
    """Подобласти работы; на записях до SFR-5 их берём из карты тем."""
    mapping = mapping or {}
    names: set[str] = set()
    for topic in work.topics or []:
        if not isinstance(topic, dict):
            continue
        display = topic.get("display_name")
        name = topic.get("subfield") or (mapping.get(str(display)) if display else None) or display
        if name:
            names.add(str(name))
    return names


def suspect_clusters(
    works: Sequence[Work], mapping: dict[str, str] | None = None
) -> tuple[int, int]:
    """Размеры двух крупнейших тематических групп работ, не связанных общей темой."""
    union = _Union(range(len(works)))
    subfields = [_work_subfields(work, mapping) for work in works]
    by_subfield: dict[str, int] = {}
    for index, names in enumerate(subfields):
        for name in names:
            first = by_subfield.setdefault(name, index)
            union.union(first, index)
    sizes = sorted((len(members) for members in union.groups().values()), reverse=True)
    return (sizes[0] if sizes else 0, sizes[1] if len(sizes) > 1 else 0)


def detect_suspect_merges(session: Session) -> dict[str, int]:
    """Отметить профили, похожие на чужую склейку OpenAlex. Флаг, не расклейка."""
    authors = list(
        session.execute(
            select(Author)
            .where(Author.is_supervisor_candidate.is_(True), Author.merged_into_id.is_(None))
            .options(selectinload(Author.works))
        ).scalars()
    )
    mapping = topic_subfields(session)
    stats = {"checked": 0, "suspect": 0}
    for author in authors:
        works = list(author.works)
        stats["checked"] += 1
        suspect = False
        if len(works) >= SUSPECT_MIN_WORKS:
            largest, second = suspect_clusters(works, mapping)
            suspect = second >= SUSPECT_MIN_SHARE * len(works) and largest > second
        author.suspect_merge = suspect
        if suspect:
            stats["suspect"] += 1
    log.info("dedup_suspect", **stats)
    return stats


def suspect_examples(session: Session, limit: int = 20) -> list[dict[str, Any]]:
    """Подозрительные профили с раскладкой по темам — для отчёта и ручной проверки."""
    authors = list(
        session.execute(
            select(Author)
            .where(Author.suspect_merge.is_(True), Author.is_supervisor_candidate.is_(True))
            .options(selectinload(Author.works), selectinload(Author.topics))
            .order_by(Author.openalex_id)
        ).scalars()
    )
    mapping = topic_subfields(session)
    out: list[dict[str, Any]] = []
    for author in authors[:limit]:
        largest, second = suspect_clusters(list(author.works), mapping)
        out.append(
            {
                "author_id": author.openalex_id,
                "name": author.display_name,
                "institution": _institution_name(author),
                "n_works": len(author.works),
                "cluster_sizes": [largest, second],
                "topics": [t.topic_name for t in sorted(author.topics, key=lambda t: -t.score)][:6],
            }
        )
    return out


def render_dedup_review(
    merges: Sequence[MergeGroup],
    namesakes: Sequence[MergeGroup],
    suspects: Sequence[dict[str, Any]],
    *,
    n_examples: int = 10,
) -> str:
    """`eval/dedup_for_review.md` — что склеено и что осталось человеку.

    Файл нужен ровно затем, зачем `judgments_for_review*.md`: решения принимал
    агент, и без выборки на глазах человека они остаются непроверенными.
    """
    lines = [
        "# Дедупликация каталога (SFR-5) — выборка на ручную проверку",
        "",
        "Готовит агент, читает человек. Ниже три раздела: что склеено "
        "автоматически, кого решено **не** склеивать, и профили с подозрением "
        "на чужую склейку OpenAlex.",
        "",
        f"Склеек: **{len(merges)}**; групп тёзок без сигнала: **{len(namesakes)}**; "
        f"профилей с флагом `suspect_merge`: **{len(suspects)}**.",
        "",
        f"## Склеено автоматически — первые {n_examples}",
        "",
        "«Канонический» — тот, у кого больше работ; на него перенесены работы, "
        "темы и счётчики остальных.",
        "",
        "| Канонический | Имена | Вуз | Дубли | Сигнал |",
        "|---|---|---|---|---|",
    ]
    for group in list(merges)[:n_examples]:
        lines.append(
            f"| `{group.canonical}` | {'; '.join(dict.fromkeys(group.names))} | "
            f"{'; '.join(dict.fromkeys(group.institutions))} | "
            f"{', '.join(f'`{d}`' for d in group.duplicates)} | {group.signal} |"
        )
    lines += [
        "",
        f"## Не склеено: тёзки — первые {n_examples}",
        "",
        "Одинаковое имя и вуз, но ни ORCID, ни общей работы. Склеить их "
        "автоматически — риск объединить двух разных людей; оставить как есть — "
        "риск дубля в выдаче. Выбран второй.",
        "",
        "| Автор-ы | Имена | Вуз |",
        "|---|---|---|",
    ]
    for group in list(namesakes)[:n_examples]:
        ids = ", ".join(f"`{i}`" for i in [group.canonical, *group.duplicates])
        lines.append(
            f"| {ids} | {'; '.join(dict.fromkeys(group.names))} | "
            f"{'; '.join(dict.fromkeys(group.institutions))} |"
        )
    lines += [
        "",
        f"## Подозрение на чужую склейку — первые {n_examples}",
        "",
        "Работы профиля распадаются на две тематические группы без общей "
        "подобласти. Расклейка не делается: делить работы между людьми, которых "
        "мы не знаем, нечем. На фронте флаг пока не показывается.",
        "",
        "| Автор | Имя | Вуз | Работ | Группы | Темы |",
        "|---|---|---|---|---|---|",
    ]
    for item in list(suspects)[:n_examples]:
        lines.append(
            f"| `{item['author_id']}` | {item['name']} | {item['institution']} | "
            f"{item['n_works']} | {item['cluster_sizes'][0]}+{item['cluster_sizes'][1]} | "
            f"{'; '.join(item['topics'][:4])} |"
        )
    return "\n".join(lines) + "\n"
