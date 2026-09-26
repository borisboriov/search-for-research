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

**ORCID — сигнал в обе стороны** (26.09, #96/#108). Проверка каталога без
квоты показала два класса ошибок: OpenAlex приклеивает один ORCID к чужому
профилю (Краева/Кожин, Жевлаков/Жеребчевский), а соавторы-родственники с одной
буквой имени склеивались по общей работе при **разных** ORCID (Лукинские
Valery/Vladislav, Корянов Vsevolod/Victor, Иноуэ Akihisa/Atsuo — все три в
боевом каталоге с SFR-5). Поэтому: один ORCID склеивает только при совпадении
фамилий; два разных ORCID запрещают склейку по любому сигналу; два разных
развёрнутых имени — тоже запрет. Такие пары уходят в отдельный список отчёта
«требуют решения человека». Сравнение имён терпимо к транслитерации
(«Андреева» = «Andreeva», «Vershubskaya» = «Vershubsky», «Alexander» =
«Aleksandr»), иначе настоящие склейки уезжали бы в review.

**Чужая склейка** — обратная беда: OpenAlex положил в один профиль работы двух
людей (NLP-специалист с «Т-клетками мышей», химик с нейтринным экспериментом).
Расклеивать автоматически нечем — работы придётся делить между людьми, которых
мы не знаем. Здесь только детектор: работы профиля кластеризуются по общим
подобластям, и если две крупные группы не имеют ни одной общей подобласти,
профиль получает флаг ``suspect_merge``. Биофизик такой детектор не ловит:
его работы связаны цепочкой общих подобластей, а не разорваны надвое.
"""

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from sfr_core.models import Author, AuthorTopic, SupervisorProfile, Work
from sfr_etl.ingest import upsert_author
from sfr_etl.works import ingest_works_for_author

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
# С какого пересечения тем такая пара попадает хотя бы в список «похоже, один
# человек» для ручного разбора (#109): ниже — обычные тёзки.
NEAR_DUPLICATE_TOPIC_OVERLAP = 1


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


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}  # fmt: skip


def fold_name(part: str) -> str:
    """Свести написание имени или фамилии к форме, терпимой к транслитерации.

    Кириллица → латиница; затем сглаживаются разночтения латинских систем
    («kh»/«h», «x»/«ks», «y»/«i», «j»/«i», «w»/«v»). Это не лингвистика, а
    минимум, при котором «Андреева» = «Andreeva», «Yury» = «Yuri»,
    «Alexander» ≈ «Aleksandr». Цель — не склеить лишнего, а не отправлять
    настоящие склейки в review из-за буквы.
    """
    text = "".join(_TRANSLIT.get(ch, ch) for ch in part.lower())
    for src, dst in (("kh", "h"), ("ph", "f"), ("x", "ks"), ("ck", "k"), ("w", "v"), ("j", "i")):
        text = text.replace(src, dst)
    text = text.replace("y", "i")
    while "ii" in text:
        text = text.replace("ii", "i")
    return text


def surname_key(display_name: str) -> str:
    """Фамилия без окончаний рода и склонения: «Vershubskaya» и «Vershubsky» — одно."""
    surname = name_key(display_name).split("|", 1)[0]
    folded = fold_name(surname)
    for suffix in ("skaia", "skaya", "ski", "sk"):
        if folded.endswith(suffix):
            return folded[: -len(suffix)] + "sk"
    if folded.endswith("aia") or folded.endswith("aya"):
        folded = folded[:-3]
    elif folded.endswith("a") and len(folded) > 4:
        folded = folded[:-1]
    return folded


def same_surname(left: str, right: str) -> bool:
    return bool(surname_key(left)) and surname_key(left) == surname_key(right)


def full_first_name(display_name: str) -> str | None:
    """Развёрнутое (не инициал) первое имя, если оно записано; иначе None.

    Части в одну-две буквы — инициалы, в том числе усечённые («Il.», «Yu.»,
    «Al.»): «Il. S. Golyak» и «Igor S. Golyak» — один человек, а не конфликт.
    """
    cleaned = _INITIALS_RE.sub(" ", display_name).lower()
    parts = [p for p in cleaned.split() if p]
    if len(parts) < 2:
        return None
    surname_at = next(
        (i for i in range(len(parts) - 1, -1, -1) if len(parts[i]) > 1), len(parts) - 1
    )
    for i, part in enumerate(parts):
        if i != surname_at and len(part) > 2:
            return part
    return None


def _levenshtein(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


# Расстояние между свёрнутыми именами, начиная с которого это разные имена,
# а не разные транслитерации: «aleksander»/«aleksandr» — 1, «mihail»/«michael» — 3.
FIRST_NAME_CONFLICT_DISTANCE = 3


def first_names_conflict(left: str, right: str) -> bool:
    """Оба имени развёрнуты и это разные имена (Valery/Vladislav, Akihisa/Atsuo).

    Инициалы не спорят ни с чем: «V. V. Koryanov» против «Vsevolod V. Koryanov»
    конфликта не даёт. Транслитерации одного имени (Yury/Yuri, Nataliya/Natalia,
    Alexander/Aleksandr) тоже не конфликт — сравниваются свёрнутые формы с
    допуском в две правки.
    """
    a, b = full_first_name(left), full_first_name(right)
    if not a or not b:
        return False
    fa, fb = fold_name(a), fold_name(b)
    if fa == fb or fa.startswith(fb) or fb.startswith(fa):
        return False
    return _levenshtein(fa, fb) >= FIRST_NAME_CONFLICT_DISTANCE


@dataclass
class MergeGroup:
    """Один человек: канонический автор и его дубли."""

    canonical: str
    duplicates: list[str]
    signal: str
    names: list[str] = field(default_factory=list)
    institutions: list[str] = field(default_factory=list)


@dataclass
class DedupFindings:
    """Результат поиска дублей: что склеить, что оставить, что отдать человеку.

    ``merges`` — склеить автоматически (плюс уже применённые); ``namesakes`` —
    одно имя и вуз без сигнала (не трогать); ``review`` — сигнал есть, но его
    блокирует конфликт ORCID или имён, решает человек; ``near_duplicates`` —
    похоже, один человек (полное имя ↔ инициалы, один вуз), но общих тем
    меньше порога — тоже человеку, отдельным списком (#109).
    """

    merges: list[MergeGroup] = field(default_factory=list)
    namesakes: list[MergeGroup] = field(default_factory=list)
    review: list[MergeGroup] = field(default_factory=list)
    near_duplicates: list[MergeGroup] = field(default_factory=list)

    def __iter__(self) -> Iterator[list[MergeGroup]]:
        """Обратная совместимость: ``merges, namesakes = find_splits(session)``."""
        return iter((self.merges, self.namesakes))


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


def recovered_signal(canonical: Author, duplicate: Author) -> str:
    """Восстановить признак, по которому пара была склеена.

    Нужно для файла ручной проверки: строка «склеено ранее» не говорит человеку
    ничего, а именно ради его глаз файл и существует. Восстанавливаем из ``raw`` —
    исходных записей OpenAlex, которые склейка не трогает.

    Признак «общая работа» после склейки невосстановим: работы дубля физически
    переехали на канонического автора. Такая пара так и помечается — честнее,
    чем подставить правдоподобный сигнал.
    """
    canonical_orcid = normalize_orcid((canonical.raw or {}).get("orcid") or canonical.orcid)
    duplicate_orcid = normalize_orcid((duplicate.raw or {}).get("orcid") or duplicate.orcid)
    if canonical_orcid and canonical_orcid == duplicate_orcid:
        return "orcid"
    shared_topics = set(_raw_topics(canonical)) & set(_raw_topics(duplicate))
    if is_abbreviation_pair(canonical, duplicate) and len(shared_topics) >= ABBREV_TOPIC_OVERLAP:
        return "abbrev+institution+topics"
    return "склеено ранее (признак не восстановить — работы уже перенесены)"


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
                signal=recovered_signal(canonical, duplicate),
                names=[canonical.display_name],
                institutions=[_institution_name(canonical)],
            )
            groups[canonical.id] = group
        group.duplicates.append(duplicate.openalex_id)
        group.names.append(duplicate.display_name)
        group.institutions.append(_institution_name(duplicate))
    return sorted(groups.values(), key=lambda g: g.canonical)


def _group(by_db_id: dict[int, Author], ids: Sequence[int], signal: str) -> MergeGroup:
    ordered = sorted(ids, key=lambda i: (-(by_db_id[i].works_count or 0), by_db_id[i].openalex_id))
    return MergeGroup(
        canonical=by_db_id[ordered[0]].openalex_id,
        duplicates=[by_db_id[i].openalex_id for i in ordered[1:]],
        signal=signal,
        names=[by_db_id[i].display_name for i in ordered],
        institutions=[_institution_name(by_db_id[i]) for i in ordered],
    )


def _blocker(left: Author, right: Author) -> str | None:
    """Почему пару нельзя склеить автоматически, даже если сигнал есть.

    Два разных непустых ORCID — два человека, что бы ни говорили имя и общая
    работа (Лукинские, Корянов, Иноуэ). Два разных развёрнутых имени — тоже
    (Valery/Vladislav); инициалы и транслитерации конфликта не дают.
    """
    left_orcid, right_orcid = normalize_orcid(left.orcid), normalize_orcid(right.orcid)
    if left_orcid and right_orcid and left_orcid != right_orcid:
        return "разные ORCID"
    if first_names_conflict(left.display_name, right.display_name):
        return "разные имена"
    return None


def find_splits(
    session: Session,
    *,
    abbrev_topic_overlap: int = ABBREV_TOPIC_OVERLAP,
    near_duplicate_topic_overlap: int = NEAR_DUPLICATE_TOPIC_OVERLAP,
) -> DedupFindings:
    """Группы для склейки, тёзки без сигнала, пары на решение человека.

    Уже применённые склейки входят в ``merges`` с сигналом «склеено ранее».
    Распаковка ``merges, namesakes = find_splits(session)`` по-прежнему
    работает; полный результат — поля :class:`DedupFindings`.
    """
    authors = _catalogue_authors(session)
    by_db_id = {a.id: a for a in authors}
    union = _Union(by_db_id)
    signals: dict[int, str] = {}
    review: list[MergeGroup] = []
    reviewed: set[tuple[int, int]] = set()

    def send_to_review(left: int, right: int, reason: str) -> None:
        key = (min(left, right), max(left, right))
        if key not in reviewed:
            reviewed.add(key)
            review.append(_group(by_db_id, [left, right], reason))

    # ORCID: склеивает только при совпадении фамилий — OpenAlex приклеивает ORCID
    # к чужим профилям, и одинаковый идентификатор у «Kraeva» и «Kozhin» — это
    # ошибка источника, а не один человек.
    by_orcid: dict[str, list[int]] = {}
    for author in authors:
        orcid = normalize_orcid(author.orcid)
        if orcid:
            by_orcid.setdefault(orcid, []).append(author.id)
    for ids in by_orcid.values():
        anchor = ids[0]
        for other in ids[1:]:
            anchor_author, other_author = by_db_id[anchor], by_db_id[other]
            if same_surname(
                anchor_author.display_name, other_author.display_name
            ) and not first_names_conflict(anchor_author.display_name, other_author.display_name):
                union.union(anchor, other)
                signals[union.find(anchor)] = "orcid"
            else:
                send_to_review(anchor, other, "один ORCID, разные фамилии или имена")

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

    near: list[MergeGroup] = []
    for ids in by_name.values():
        if len(ids) < 2:
            continue
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                overlap = len(top_topics.get(left, set()) & top_topics.get(right, set()))
                abbreviation = is_abbreviation_pair(by_db_id[left], by_db_id[right])
                signal: str | None = None
                if shared.get(left, set()) & shared.get(right, set()):
                    signal = "name+institution+work"
                elif abbreviation and overlap >= abbrev_topic_overlap:
                    signal = "abbrev+institution+topics"
                if signal is None:
                    if abbreviation and overlap >= near_duplicate_topic_overlap:
                        near.append(
                            _group(
                                by_db_id,
                                [left, right],
                                f"полное имя ↔ инициалы, один вуз, общих тем {overlap}",
                            )
                        )
                    continue
                blocker = _blocker(by_db_id[left], by_db_id[right])
                if blocker is not None:
                    send_to_review(left, right, f"{signal}, но {blocker}")
                    continue
                union.union(left, right)
                signals.setdefault(union.find(left), signal)

    # Тёзки: одно имя и один вуз, но ни одного сигнала о личности. Автоматически
    # не трогаем — только в отчёт, на глаза человеку.
    near_ids = {(g.canonical, tuple(g.duplicates)) for g in near}
    review_ids = {(g.canonical, tuple(g.duplicates)) for g in review}
    namesakes: list[MergeGroup] = []
    for ids in by_name.values():
        if len(ids) < 2 or len({union.find(i) for i in ids}) == 1:
            continue
        ordered = sorted(ids, key=lambda i: by_db_id[i].openalex_id)
        group = MergeGroup(
            canonical=by_db_id[ordered[0]].openalex_id,
            duplicates=[by_db_id[i].openalex_id for i in ordered[1:]],
            signal="одно имя и вуз, общих работ и ORCID нет — не склеиваем",
            names=[by_db_id[i].display_name for i in ordered],
            institutions=[_institution_name(by_db_id[i]) for i in ordered],
        )
        member_ids = {group.canonical, *group.duplicates}
        listed = any({c, *d} <= member_ids for c, d in near_ids | review_ids)
        if len(member_ids) == 2 and listed:
            continue  # пара уже стоит в более информативном списке
        namesakes.append(group)

    merges: list[MergeGroup] = []
    for root, members in union.groups().items():
        if len(members) < 2:
            continue
        merges.append(_group(by_db_id, members, signals.get(root, "orcid")))
    merges.sort(key=lambda g: g.canonical)
    namesakes.sort(key=lambda g: g.canonical)
    review.sort(key=lambda g: g.canonical)
    near.sort(key=lambda g: g.canonical)
    return DedupFindings(
        merges=applied_merges(session) + merges,
        namesakes=namesakes,
        review=review,
        near_duplicates=near,
    )


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


def _raw_counters(author: Author) -> tuple[int, int, int | None]:
    """``works_count``, ``cited_by_count``, ``h_index`` из исходной записи OpenAlex."""
    raw = author.raw or {}
    summary = raw.get("summary_stats") or {}
    return (
        int(raw.get("works_count") or 0),
        int(raw.get("cited_by_count") or 0),
        summary.get("h_index"),
    )


def _raw_topics(author: Author) -> dict[str, float]:
    """Темы автора из ``raw``: имя → score (``count``), как их кладёт ``upsert_author``."""
    topics: dict[str, float] = {}
    for topic in (author.raw or {}).get("topics") or []:
        name = topic.get("display_name")
        if name:
            topics[str(name)] = topics.get(str(name), 0.0) + float(topic.get("count") or 0)
    return topics


def recompute_merged_aggregates(session: Session, *, dry_run: bool = False) -> dict[str, int]:
    """Пересобрать счётчики и темы канонических авторов из ``raw``.

    Зачем отдельный проход. ``apply_merges`` складывает ``works_count`` и
    ``cited_by_count`` канонического автора с дублями и берёт максимальный
    ``h_index``, но следующий же ``sfr etl authors`` перезаписывает эти колонки
    свежими значениями OpenAlex и заново заливает темы (``upsert_author``) —
    результат склейки пропадает молча. Повторная склейка его не вернёт: дубли
    с проставленным ``merged_into_id`` пропускаются.

    Поэтому агрегаты здесь не «досчитываются», а **собираются заново** из
    ``Author.raw`` — нетронутых записей OpenAlex канонического автора и всех его
    дублей. Функция идемпотентна по построению: текущие значения колонок она не
    читает вовсе, только сравнивает с ними результат. Запускать после любого
    ингеста авторов; на каталоге без склеек это no-op.

    Группы, где у кого-то нет ``raw`` (данные из старых прогонов), пропускаются:
    достроить их не из чего, а испортить существующие значения — можно.
    """
    stats = {"canonical": 0, "changed": 0, "skipped_no_raw": 0, "topics_rebuilt": 0}
    canonical_ids = [
        row
        for (row,) in session.execute(
            select(Author.merged_into_id).where(Author.merged_into_id.is_not(None)).distinct()
        )
    ]
    for canonical_id in canonical_ids:
        canonical = session.get(Author, canonical_id)
        if canonical is None:  # pragma: no cover — FK гарантирует наличие
            continue
        duplicates = list(
            session.execute(select(Author).where(Author.merged_into_id == canonical.id)).scalars()
        )
        stats["canonical"] += 1
        cluster = [canonical, *duplicates]
        if any(author.raw is None for author in cluster):
            stats["skipped_no_raw"] += 1
            continue

        works = cited = 0
        h_indexes: list[int] = []
        topics: dict[str, float] = {}
        orcid = None
        for author in cluster:
            author_works, author_cited, author_h = _raw_counters(author)
            works += author_works
            cited += author_cited
            if author_h is not None:
                h_indexes.append(int(author_h))
            for name, score in _raw_topics(author).items():
                topics[name] = topics.get(name, 0.0) + score
            orcid = orcid or (author.raw or {}).get("orcid")
        h_index = max(h_indexes) if h_indexes else None

        current_topics = {
            topic.topic_name: topic.score
            for topic in session.execute(
                select(AuthorTopic).where(AuthorTopic.author_id == canonical.id)
            ).scalars()
        }
        counters_differ = (
            canonical.works_count != works
            or canonical.cited_by_count != cited
            or canonical.h_index != h_index
            or canonical.orcid != orcid
        )
        topics_differ = current_topics != topics
        if not counters_differ and not topics_differ:
            continue
        stats["changed"] += 1
        if dry_run:
            log.info(
                "dedup_aggregates_would_change",
                author=canonical.openalex_id,
                works_count=(canonical.works_count, works),
                h_index=(canonical.h_index, h_index),
                topics=(len(current_topics), len(topics)),
            )
            continue

        canonical.works_count = works
        canonical.cited_by_count = cited
        canonical.h_index = h_index
        canonical.orcid = orcid
        if topics_differ:
            session.execute(delete(AuthorTopic).where(AuthorTopic.author_id == canonical.id))
            session.flush()
            for name, score in topics.items():
                session.add(AuthorTopic(author_id=canonical.id, topic_name=name, score=score))
            stats["topics_rebuilt"] += 1
    log.info("dedup_aggregates", dry_run=dry_run, **stats)
    return stats


class UnmergeError(ValueError):
    """Расклейка невозможна или небезопасна; текст — для человека в CLI."""


def unmerge_author(
    session: Session,
    client: Any,
    duplicate_openalex_id: str,
    settings: Any,
    *,
    dry_run: bool = True,
    current_year: int | None = None,
) -> dict[str, Any]:
    """Развести ошибочно склеенный дубль и его канонического автора.

    Склейка необратима в пределах БД: работы дубля физически переехали на
    канонического, счётчики сложены. Поэтому расклейка — не откат, а
    **восстановление обоих из источников**: агрегаты и темы — из ``raw``
    (``upsert_author``), работы — заново из дискового кэша OpenAlex
    (``ingest_works_for_author``; если работ дубля в кэше нет — два сетевых
    запроса, число печатается). Профили обоих удаляются — их пересоберёт
    ``sfr etl build-profiles``; флаг ``suspect_merge`` сбрасывается до
    следующего ``dedup``.

    Отказывается работать, если у канонического есть **другие** дубли: их
    перенесённые работы при переингесте канонического потерялись бы. Такие
    группы разбираются вручную. Идемпотентна: неcклеенный id — no-op.
    """
    duplicate = session.execute(
        select(Author).where(Author.openalex_id == duplicate_openalex_id)
    ).scalar_one_or_none()
    if duplicate is None:
        raise UnmergeError(f"{duplicate_openalex_id}: автора нет в БД")
    if duplicate.merged_into_id is None:
        return {"duplicate": duplicate_openalex_id, "status": "not_merged", "changed": False}
    canonical = session.get(Author, duplicate.merged_into_id)
    if canonical is None:  # pragma: no cover — FK гарантирует наличие
        raise UnmergeError(f"{duplicate_openalex_id}: канонический автор не найден")
    siblings = [
        a.openalex_id
        for a in session.execute(
            select(Author).where(Author.merged_into_id == canonical.id, Author.id != duplicate.id)
        ).scalars()
    ]
    if siblings:
        raise UnmergeError(
            f"{duplicate_openalex_id}: у канонического {canonical.openalex_id} есть другие "
            f"дубли {siblings} — переингест потерял бы их работы; разбирать вручную"
        )
    if duplicate.raw is None or canonical.raw is None:
        raise UnmergeError(f"{duplicate_openalex_id}: нет raw-записи, восстановить не из чего")

    works_before = session.execute(select(Work.id).where(Work.author_id == canonical.id)).all()
    stats: dict[str, Any] = {
        "duplicate": duplicate_openalex_id,
        "canonical": canonical.openalex_id,
        "status": "planned" if dry_run else "unmerged",
        "changed": not dry_run,
        "works_on_canonical_before": len(works_before),
        "raw_works_count": {
            canonical.openalex_id: int((canonical.raw or {}).get("works_count") or 0),
            duplicate.openalex_id: int((duplicate.raw or {}).get("works_count") or 0),
        },
    }
    if dry_run:
        return stats

    for author in (canonical, duplicate):
        session.execute(delete(Work).where(Work.author_id == author.id))
        session.execute(delete(SupervisorProfile).where(SupervisorProfile.author_id == author.id))
    duplicate.merged_into_id = None
    session.flush()
    restored: dict[str, int] = {}
    for author in (canonical, duplicate):
        # upsert_author восстанавливает счётчики, ORCID, темы и флаг кандидата
        # из нетронутой записи OpenAlex; вуз остаётся прежним.
        raw, institution_id = author.raw, author.last_known_institution_id
        if raw is None or institution_id is None:  # pragma: no cover — проверено выше
            raise UnmergeError(f"{author.openalex_id}: нет raw или вуза")
        upsert_author(session, raw, institution_id, settings, current_year=current_year)
        author.suspect_merge = False
        result = ingest_works_for_author(
            session,
            client,
            author,
            since_years=settings.works_since_years,
            per_author=settings.works_per_author,
            current_year=current_year,
        )
        restored[author.openalex_id] = result["saved"]
    session.flush()
    stats["works_after"] = restored
    log.info("dedup_unmerged", **{k: v for k, v in stats.items() if k != "raw_works_count"})
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
            # >= , а не > : профиль, ровно пополам расщеплённый между двумя
            # людьми (6 + 6 из 12), — самая подозрительная форма из возможных.
            suspect = second >= SUSPECT_MIN_SHARE * len(works) and largest >= second
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


def _first(n_examples: int, total: int) -> str:
    return f"все {total}" if n_examples >= total else f"первые {n_examples} из {total}"


def render_dedup_review(
    merges: Sequence[MergeGroup],
    namesakes: Sequence[MergeGroup],
    suspects: Sequence[dict[str, Any]],
    *,
    n_suspects: int | None = None,
    n_examples: int = 10,
    review: Sequence[MergeGroup] = (),
    near_duplicates: Sequence[MergeGroup] = (),
) -> str:
    """`eval/dedup_for_review.md` — что склеено и что осталось человеку.

    Файл нужен ровно затем, зачем `judgments_for_review*.md`: решения принимал
    агент, и без выборки на глазах человека они остаются непроверенными.

    ``suspects`` — уже обрезанная выборка для таблицы, поэтому масштаб
    (``n_suspects``) передаётся отдельно: печатать в шапке её длину значит
    показывать человеку размер примера вместо размера проблемы.
    """
    n_suspects = len(suspects) if n_suspects is None else n_suspects
    lines = [
        "# Дедупликация каталога (SFR-5) — выборка на ручную проверку",
        "",
        "Готовит агент, читает человек. Ниже три раздела: что склеено "
        "автоматически, кого решено **не** склеивать, и профили с подозрением "
        "на чужую склейку OpenAlex.",
        "",
        f"Склеек: **{len(merges)}**; требуют решения человека: **{len(review)}**; "
        f"похоже, один человек, но сигнала не хватило: **{len(near_duplicates)}**; "
        f"групп тёзок без сигнала: **{len(namesakes)}**; "
        f"профилей с флагом `suspect_merge`: **{n_suspects}**.",
        "",
        f"## Склеено автоматически — {_first(n_examples, len(merges))}",
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
        f"## Требуют решения человека — {_first(n_examples, len(review))}",
        "",
        "Сигнал склейки есть (ORCID, общая работа или инициалы + темы), но его "
        "блокирует конфликт: один ORCID при разных фамилиях (ошибка OpenAlex), "
        "два разных ORCID или два разных развёрнутых имени. Автоматически не "
        "склеиваем; вердикт — комментарием в issue, склейка руками через "
        "`sfr etl dedup` после правки данных или расклейка `sfr etl unmerge`.",
        "",
        "| Авторы | Имена | Вуз | Причина |",
        "|---|---|---|---|",
    ]
    for group in list(review)[:n_examples]:
        ids = ", ".join(f"`{i}`" for i in [group.canonical, *group.duplicates])
        lines.append(
            f"| {ids} | {'; '.join(dict.fromkeys(group.names))} | "
            f"{'; '.join(dict.fromkeys(group.institutions))} | {group.signal} |"
        )
    lines += [
        "",
        f"## Похоже, один человек, но сигнала не хватило — "
        f"{_first(n_examples, len(near_duplicates))}",
        "",
        "Полное имя ↔ инициалы, один вуз, общих тем меньше порога склейки. "
        "Не склеиваем автоматически; список для человека (#109).",
        "",
        "| Авторы | Имена | Вуз | Что совпало |",
        "|---|---|---|---|",
    ]
    for group in list(near_duplicates)[:n_examples]:
        ids = ", ".join(f"`{i}`" for i in [group.canonical, *group.duplicates])
        lines.append(
            f"| {ids} | {'; '.join(dict.fromkeys(group.names))} | "
            f"{'; '.join(dict.fromkeys(group.institutions))} | {group.signal} |"
        )
    lines += [
        "",
        f"## Не склеено: тёзки — {_first(n_examples, len(namesakes))}",
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
        f"## Подозрение на чужую склейку — {_first(n_examples, n_suspects)}",
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
