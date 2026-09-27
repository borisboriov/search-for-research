"""Дедупликация авторов (SPEC_SFR5 §3): склейка расщеплённых и флаг чужой склейки."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session
from test_ingest import INSTITUTION_RECORD, author_record
from test_works import work_record

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Author, AuthorTopic, Work
from sfr_core.settings import Settings
from sfr_etl.dedup import (
    DEFAULT_DECISIONS_PATH,
    INITIALS_BOTH,
    INITIALS_ONE_FULL,
    STATUS_ALREADY_MERGED,
    STATUS_BAN_ACTIVE,
    STATUS_FORBIDDEN_BUT_MERGED,
    STATUS_MERGED_BY_HUMAN,
    STATUS_NOT_IN_CATALOGUE,
    DecisionsFileMissing,
    DedupDecision,
    MergeGroup,
    UnmergeError,
    apply_merges,
    detect_suspect_merges,
    find_splits,
    first_names_conflict,
    initials_prefix_pair,
    is_abbreviation_pair,
    load_decisions_or_fail,
    load_dedup_decisions,
    name_key,
    normalize_orcid,
    recompute_merged_aggregates,
    render_dedup_review,
    same_surname,
    suspect_examples,
    unmerge_author,
)
from sfr_etl.ingest import upsert_author, upsert_institution
from sfr_etl.works import ingest_works, upsert_work

SETTINGS = Settings(_env_file=None, openalex_mailto="test@example.com")  # type: ignore[call-arg]


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    db_url = f"sqlite:///{tmp_path}/test.db"
    upgrade_to_head(db_url)
    return make_engine(db_url)


def record(short_id: str, name: str, orcid: str | None = None, works: int = 50) -> dict[str, Any]:
    base = author_record(short_id)
    base["display_name"] = name
    base["orcid"] = orcid
    base["works_count"] = works
    return base


def topical_work(work_id: str, subfield: str, year: int = 2024) -> dict[str, Any]:
    payload = work_record(work_id, year=year)
    payload["topics"] = [
        {"display_name": f"{subfield} topic", "score": 0.9, "subfield": {"display_name": subfield}}
    ]
    return payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://orcid.org/0000-0002-1825-0097", "0000-0002-1825-0097"),
        ("0000-0002-1825-0097", "0000-0002-1825-0097"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_orcid(raw: str | None, expected: str | None) -> None:
    assert normalize_orcid(raw) == expected


def test_name_key_matches_forms_of_one_person() -> None:
    assert name_key("T. Aushev") == name_key("Timofey Aushev") == name_key("Aushev T.")


def test_name_key_separates_namesakes_and_initial_order() -> None:
    # Самая длинная часть — не фамилия: иначе все «Alexander …» стали бы тёзками.
    assert name_key("Alexander Karpov") != name_key("Alexander Kuznetsov")
    # Порядок инициалов различает людей: на живых данных это соавторы, не дубли.
    assert name_key("A. M. Kondratenko") != name_key("M. A. Kondratenko")


def test_is_abbreviation_pair() -> None:
    class Fake:
        def __init__(self, name: str) -> None:
            self.display_name = name

    assert is_abbreviation_pair(Fake("Dmitry D. Sokoloff"), Fake("D. D. Sokoloff"))  # type: ignore[arg-type]
    assert not is_abbreviation_pair(Fake("А. Е. Романов"), Fake("А. Е. Романов"))  # type: ignore[arg-type]


def test_merge_by_orcid_moves_works_and_sums_counters(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        orcid = "https://orcid.org/0000-0002-1825-0097"
        big = upsert_author(session, record("A1", "T. Aushev", orcid, 900), inst.id, SETTINGS)
        small = upsert_author(session, record("A2", "Timofey Aushev", orcid, 80), inst.id, SETTINGS)
        upsert_work(session, topical_work("W1", "Nuclear Physics"), big.id, since_year=2022)
        upsert_work(session, topical_work("W2", "Nuclear Physics"), small.id, since_year=2022)
        session.add(AuthorTopic(author_id=small.id, topic_name="Neutrino", score=3.0))

    with session_scope(engine) as session:
        merges, namesakes = find_splits(session)
        assert [g.signal for g in merges] == ["orcid"]
        assert merges[0].canonical == "A1"  # канонический — тот, у кого больше работ
        assert namesakes == []
        stats = apply_merges(session, merges)
        assert stats == {"groups": 1, "duplicates": 1, "works_moved": 1, "works_dropped": 0}

    with session_scope(engine) as session:
        canonical = session.execute(select(Author).where(Author.openalex_id == "A1")).scalar_one()
        duplicate = session.execute(select(Author).where(Author.openalex_id == "A2")).scalar_one()
        assert canonical.works_count == 980
        assert {w.openalex_id for w in canonical.works} == {"W1", "W2"}
        assert duplicate.merged_into_id == canonical.id
        assert duplicate.is_supervisor_candidate is False


def test_namesakes_without_a_signal_are_reported_not_merged(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        for short_id in ("A1", "A2"):
            author = upsert_author(session, record(short_id, "А. Е. Романов"), inst.id, SETTINGS)
            upsert_work(session, topical_work(f"W{short_id}", "Optics"), author.id, since_year=2022)

    with session_scope(engine) as session:
        merges, namesakes = find_splits(session)
        assert merges == []
        assert len(namesakes) == 1
        assert sorted([namesakes[0].canonical, *namesakes[0].duplicates]) == ["A1", "A2"]


def test_apply_merges_is_idempotent(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        orcid = "https://orcid.org/0000-0003-0000-0001"
        upsert_author(session, record("A1", "Qiang Wang", orcid, 300), inst.id, SETTINGS)
        upsert_author(session, record("A2", "Qiang Wang", orcid, 100), inst.id, SETTINGS)

    with session_scope(engine) as session:
        merges, _ = find_splits(session)
        apply_merges(session, merges)
    with session_scope(engine) as session:
        # Повторный прогон видит склейку как уже применённую и не удваивает счётчики.
        merges, _ = find_splits(session)
        # Признак восстанавливается из raw, а не подменяется на «склеено ранее».
        assert [g.signal for g in merges] == ["orcid"]
        apply_merges(session, merges)
        canonical = session.execute(select(Author).where(Author.openalex_id == "A1")).scalar_one()
        assert canonical.works_count == 400


def test_suspect_merge_flags_two_unconnected_groups(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        mixed = upsert_author(session, record("A1", "Split Person"), inst.id, SETTINGS)
        clean = upsert_author(session, record("A2", "Whole Person"), inst.id, SETTINGS)
        for i in range(7):
            upsert_work(session, topical_work(f"WA{i}", "Immunology"), mixed.id, since_year=2022)
        for i in range(5):
            upsert_work(
                session,
                topical_work(f"WB{i}", "Artificial Intelligence"),
                mixed.id,
                since_year=2022,
            )
        for i in range(10):
            upsert_work(session, topical_work(f"WC{i}", "Optics"), clean.id, since_year=2022)

    with session_scope(engine) as session:
        stats = detect_suspect_merges(session)
        assert stats == {"checked": 2, "suspect": 1}
        examples = suspect_examples(session)
        assert [e["author_id"] for e in examples] == ["A1"]
        assert examples[0]["cluster_sizes"] == [7, 5]


def test_review_file_has_all_three_sections(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        upsert_author(session, record("A1", "Solo Person"), inst.id, SETTINGS)
        merges, namesakes = find_splits(session)
        text = render_dedup_review(merges, namesakes, [])
    assert "## Склеено автоматически" in text
    assert "## Не склеено: тёзки" in text
    assert "## Подозрение на чужую склейку" in text


def test_review_header_shows_suspect_count_not_sample_size(engine: Engine) -> None:
    """В шапке — масштаб проблемы, а не длина обрезанной выборки (ревью SFR-5)."""
    sample = [
        {
            "author_id": f"A{i}",
            "name": f"Person {i}",
            "institution": "Some University",
            "n_works": 20,
            "cluster_sizes": [12, 8],
            "topics": ["Optics"],
        }
        for i in range(20)
    ]
    text = render_dedup_review([], [], sample, n_suspects=143, n_examples=10)
    assert "профилей с флагом `suspect_merge`: **143**" in text
    assert "первые 10 из 143" in text


def test_mega_collaboration_counter_is_stored(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        author = upsert_author(session, record("A1", "Physicist"), inst.id, SETTINGS)
        payload = work_record("W1")
        payload["institutions_distinct_count"] = 211
        upsert_work(session, payload, author.id, since_year=2022)
    with session_scope(engine) as session:
        work = session.execute(select(Work).where(Work.openalex_id == "W1")).scalar_one()
        assert work.institutions_distinct_count == 211


class CountingWorksClient:
    """Считает, за сколько авторов ингест пошёл в сеть; тела ответов пустые."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append(params or {})
        return {"results": []}


def test_ingest_works_skips_merged_duplicates(engine: Engine) -> None:
    """Дубль не должен возвращаться в очередь работ после повторного ингеста авторов.

    `upsert_author` пересчитывает `is_supervisor_candidate` из эвристики и про
    склейку не знает — значит один этот флаг дубля не удерживает, и без фильтра
    по `merged_into_id` каждый дубль стоил бы двух запросов дневной квоты.
    """
    orcid = "https://orcid.org/0000-0004-0000-0002"
    with session_scope(engine) as session:
        inst_id = upsert_institution(session, INSTITUTION_RECORD).id
        upsert_author(session, record("A1", "T. Aushev", orcid, 900), inst_id, SETTINGS)
        upsert_author(session, record("A2", "Timofey Aushev", orcid, 80), inst_id, SETTINGS)
    with session_scope(engine) as session:
        merges, _ = find_splits(session)
        apply_merges(session, merges)
        # Повторный ингест авторов: флаг кандидата дублю возвращается.
        upsert_author(session, record("A2", "Timofey Aushev", orcid, 80), inst_id, SETTINGS)

    with session_scope(engine) as session:
        duplicate = session.execute(select(Author).where(Author.openalex_id == "A2")).scalar_one()
        assert duplicate.is_supervisor_candidate is True, "флаг действительно восстановился"
        assert duplicate.merged_into_id is not None
        client = CountingWorksClient()
        totals = ingest_works(session, client, since_years=5, per_author=5)  # type: ignore[arg-type]
    assert totals["authors"] == 1, "в очередь попал только канонический автор"
    assert len(client.calls) == 2, "два запроса на одного автора, а не на двух"


def test_recompute_restores_aggregates_after_reingest(engine: Engine) -> None:
    """Повторный ингест затирает агрегаты склейки — пересчёт из raw их возвращает."""
    orcid = "https://orcid.org/0000-0004-0000-0003"
    with session_scope(engine) as session:
        inst_id = upsert_institution(session, INSTITUTION_RECORD).id
        upsert_author(session, record("A1", "T. Aushev", orcid, 900), inst_id, SETTINGS)
        upsert_author(session, record("A2", "Timofey Aushev", orcid, 80), inst_id, SETTINGS)
    with session_scope(engine) as session:
        merges, _ = find_splits(session)
        apply_merges(session, merges)
    with session_scope(engine) as session:
        canonical = session.execute(select(Author).where(Author.openalex_id == "A1")).scalar_one()
        assert canonical.works_count == 980, "склейка сложила счётчики"
        # Повторный ингест канонического автора: OpenAlex отдаёт только его 900.
        upsert_author(session, record("A1", "T. Aushev", orcid, 900), inst_id, SETTINGS)
    with session_scope(engine) as session:
        canonical = session.execute(select(Author).where(Author.openalex_id == "A1")).scalar_one()
        assert canonical.works_count == 900, "агрегат склейки затёрт — это и есть дефект"
        stats = recompute_merged_aggregates(session)
        assert stats["changed"] == 1
    with session_scope(engine) as session:
        canonical = session.execute(select(Author).where(Author.openalex_id == "A1")).scalar_one()
        assert canonical.works_count == 980, "пересчёт из raw вернул агрегат"


def test_recompute_is_idempotent(engine: Engine) -> None:
    """Считает из raw, а не из колонок, поэтому второй прогон — ничего не меняет."""
    orcid = "https://orcid.org/0000-0004-0000-0004"
    with session_scope(engine) as session:
        inst_id = upsert_institution(session, INSTITUTION_RECORD).id
        upsert_author(session, record("A1", "Qiang Wang", orcid, 300), inst_id, SETTINGS)
        upsert_author(session, record("A2", "Qiang Wang", orcid, 100), inst_id, SETTINGS)
    with session_scope(engine) as session:
        merges, _ = find_splits(session)
        apply_merges(session, merges)
    with session_scope(engine) as session:
        assert recompute_merged_aggregates(session)["changed"] == 0, "склейка уже дала это же"
    with session_scope(engine) as session:
        assert recompute_merged_aggregates(session)["changed"] == 0
        canonical = session.execute(select(Author).where(Author.openalex_id == "A1")).scalar_one()
        assert canonical.works_count == 400, "счётчик не удвоился"


def test_recovered_signal_is_readable_not_hardcoded(engine: Engine) -> None:
    """В файле на ручную проверку должен стоять признак склейки, а не «склеено ранее»."""
    orcid = "https://orcid.org/0000-0004-0000-0005"
    with session_scope(engine) as session:
        inst_id = upsert_institution(session, INSTITUTION_RECORD).id
        upsert_author(session, record("A1", "T. Aushev", orcid, 900), inst_id, SETTINGS)
        upsert_author(session, record("A2", "Timofey Aushev", orcid, 80), inst_id, SETTINGS)
    with session_scope(engine) as session:
        merges, _ = find_splits(session)
        apply_merges(session, merges)
    with session_scope(engine) as session:
        merges, _ = find_splits(session)
        assert [g.signal for g in merges] == ["orcid"], "признак восстановлен из raw"


def test_ingest_works_only_missing_skips_authors_that_have_works(engine: Engine) -> None:
    """Повторный проход не должен стоить двух запросов квоты на уже загруженного автора."""
    with session_scope(engine) as session:
        inst_id = upsert_institution(session, INSTITUTION_RECORD).id
        loaded = upsert_author(session, record("A1", "Есть работы"), inst_id, SETTINGS)
        upsert_author(session, record("A2", "Работ нет"), inst_id, SETTINGS)
        upsert_work(session, topical_work("W1", "Optics"), loaded.id, since_year=2022)

    with session_scope(engine) as session:
        client = CountingWorksClient()
        totals = ingest_works(session, client, since_years=5, per_author=5, only_missing=True)  # type: ignore[arg-type]
    assert totals["authors"] == 1, "в сеть пошли только те, у кого работ нет"
    assert len(client.calls) == 2

    with session_scope(engine) as session:
        client = CountingWorksClient()
        ingest_works(session, client, since_years=5, per_author=5)  # type: ignore[arg-type]
    assert len(client.calls) == 4, "без флага ходим за обоими — прежнее поведение"


# --- ORCID в обе стороны и конфликты имён (26.09, #96, #108, #109) -------------


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("Т. В. Андреева", "Tatyana V. Andreeva", True),  # кириллица ↔ латиница
        ("Galina Vershubskaya", "Galina Vershubsky", True),  # -aya ↔ -y
        ("E. P. Kharitonova", "Elena P. Haritonova", True),  # kh ↔ h
        ("Svetlana G. Jorstad", "S. G. Jorstad", True),
        ("A. Yu. Kraeva", "M. A. Kozhin", False),  # один ORCID у разных людей
        ("A. P. Zhevlakov", "V. Zherebchevskii", False),
    ],
)
def test_same_surname_survives_transliteration(left: str, right: str, expected: bool) -> None:
    assert same_surname(left, right) is expected


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("Valery Lukinskiy", "Vladislav Lukinskiy", True),
        ("Vsevolod V. Koryanov", "Victor V. Koryanov", True),
        ("Akihisa Inoue", "Atsuo Inoue", True),
        ("Alexander Karpov", "Aleksandr Karpov", False),  # транслитерация — не конфликт
        ("Yury Ivanov", "Yuri Ivanov", False),
        ("Nataliya Petrova", "Natalia Petrova", False),
        ("Andrey Popov", "Андрей Попов", False),
        ("Alexey Smirnov", "Aleksei Smirnov", False),
        ("V. V. Koryanov", "Vsevolod V. Koryanov", False),  # инициал ни с чем не спорит
        ("Igor S. Golyak", "Il. S. Golyak", False),  # усечённый инициал — тоже инициал
        ("Yu. A. Zolotov", "Yuri A. Zolotov", False),
    ],
)
def test_first_names_conflict_oracle(left: str, right: str, expected: bool) -> None:
    assert first_names_conflict(left, right) is expected


def test_same_orcid_with_different_surnames_goes_to_review(engine: Engine) -> None:
    """Один ORCID у «Kraeva» и «Kozhin» — ошибка OpenAlex, а не один человек."""
    orcid = "https://orcid.org/0000-0003-0495-6694"
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        upsert_author(session, record("A1", "A. Yu. Kraeva", orcid, 40), inst.id, SETTINGS)
        upsert_author(session, record("A2", "M. A. Kozhin", orcid, 20), inst.id, SETTINGS)
    with session_scope(engine) as session:
        findings = find_splits(session)
        assert findings.merges == []
        assert [g.signal for g in findings.review] == ["один ORCID, разные фамилии или имена"]
        assert sorted([findings.review[0].canonical, *findings.review[0].duplicates]) == [
            "A1",
            "A2",
        ]


def test_same_orcid_transliterated_surname_still_merges(engine: Engine) -> None:
    orcid = "https://orcid.org/0000-0003-0000-0001"
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        upsert_author(session, record("A1", "Т. В. Андреева", orcid, 40), inst.id, SETTINGS)
        upsert_author(session, record("A2", "Tatyana V. Andreeva", orcid, 20), inst.id, SETTINGS)
    with session_scope(engine) as session:
        findings = find_splits(session)
        assert [g.signal for g in findings.merges] == ["orcid"]
        assert findings.review == []


def test_common_work_with_different_orcids_goes_to_review(engine: Engine) -> None:
    """Лукинские: одна фамилия, одна буква имени, общая работа — но два ORCID."""
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        father = upsert_author(
            session,
            record("A1", "Valery Lukinskiy", "https://orcid.org/0000-0002-2497-8826", 85),
            inst.id,
            SETTINGS,
        )
        son = upsert_author(
            session,
            record("A2", "Vladislav Lukinskiy", "https://orcid.org/0009-0004-4716-3090", 41),
            inst.id,
            SETTINGS,
        )
        upsert_work(session, topical_work("W1", "Logistics"), father.id, since_year=2022)
        upsert_work(session, topical_work("W1", "Logistics"), son.id, since_year=2022)
    with session_scope(engine) as session:
        findings = find_splits(session)
        assert findings.merges == []
        assert [g.signal for g in findings.review] == ["name+institution+work, но разные ORCID"]
        assert findings.namesakes == [], "пара в review, среди тёзок не дублируется"


def test_common_work_with_different_full_names_goes_to_review(engine: Engine) -> None:
    """Без ORCID разные развёрнутые имена тоже блокируют склейку по общей работе."""
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        left = upsert_author(
            session, record("A1", "Vsevolod V. Koryanov", None, 82), inst.id, SETTINGS
        )
        right = upsert_author(
            session, record("A2", "Victor V. Koryanov", None, 47), inst.id, SETTINGS
        )
        upsert_work(session, topical_work("W1", "Spacecraft"), left.id, since_year=2022)
        upsert_work(session, topical_work("W1", "Spacecraft"), right.id, since_year=2022)
    with session_scope(engine) as session:
        findings = find_splits(session)
        assert findings.merges == []
        assert [g.signal for g in findings.review] == ["name+institution+work, но разные имена"]


def test_near_duplicates_are_listed_apart_from_namesakes(engine: Engine) -> None:
    """«Ilya A. Ryzhikov» и «I. A. Ryzhikov» с одной общей темой — не тёзки, а кандидаты."""
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        full = upsert_author(session, record("A1", "Ilya A. Ryzhikov", None, 30), inst.id, SETTINGS)
        short = upsert_author(session, record("A2", "I. A. Ryzhikov", None, 12), inst.id, SETTINGS)
        namesake_a = upsert_author(
            session, record("A3", "Anton Chernyavskiy", None, 30), inst.id, SETTINGS
        )
        namesake_b = upsert_author(
            session, record("A4", "Andrey Chernyavskiy", None, 20), inst.id, SETTINGS
        )
        for author, names in (
            (full, ["Optics", "Lasers", "Plasma"]),
            (short, ["Optics", "Chemistry", "Biology"]),
            (namesake_a, ["Sociology"]),
            (namesake_b, ["Economics"]),
        ):
            session.execute(delete(AuthorTopic).where(AuthorTopic.author_id == author.id))
            for score, name in enumerate(names, start=1):
                session.add(AuthorTopic(author_id=author.id, topic_name=name, score=float(score)))
    with session_scope(engine) as session:
        findings = find_splits(session)
        assert findings.merges == []
        assert [sorted([g.canonical, *g.duplicates]) for g in findings.near_duplicates] == [
            ["A1", "A2"]
        ]
        assert "общих тем 1" in findings.near_duplicates[0].signal
        assert [sorted([g.canonical, *g.duplicates]) for g in findings.namesakes] == [["A3", "A4"]]


class PerAuthorWorksClient:
    """Кэш работ: отдаёт работы по author-id из фильтра запроса."""

    def __init__(self, works: dict[str, list[dict[str, Any]]]) -> None:
        self.works = works
        self.calls = 0

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls += 1
        author = (params or {}).get("filter", "").split("authorships.author.id:")[1].split(",")[0]
        return {"results": self.works.get(author, [])}


def test_unmerge_restores_both_authors_from_cache(engine: Engine) -> None:
    orcid = "https://orcid.org/0000-0002-1825-0097"
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        big = upsert_author(session, record("A1", "T. Aushev", orcid, 900), inst.id, SETTINGS)
        small = upsert_author(session, record("A2", "Timofey Aushev", orcid, 80), inst.id, SETTINGS)
        upsert_work(session, topical_work("W1", "Nuclear Physics"), big.id, since_year=2022)
        upsert_work(session, topical_work("W2", "Nuclear Physics"), small.id, since_year=2022)
    with session_scope(engine) as session:
        apply_merges(session, find_splits(session).merges)
    client = PerAuthorWorksClient(
        {
            "A1": [topical_work("W1", "Nuclear Physics")],
            "A2": [topical_work("W2", "Nuclear Physics"), topical_work("W3", "Nuclear Physics")],
        }
    )
    with session_scope(engine) as session:
        plan = unmerge_author(session, client, "A2", SETTINGS, dry_run=True)
        assert plan["status"] == "planned" and plan["works_on_canonical_before"] == 2
        assert client.calls == 0, "dry-run ничего не качает"
    with session_scope(engine) as session:
        duplicate = session.execute(select(Author).where(Author.openalex_id == "A2")).scalar_one()
        assert duplicate.merged_into_id is not None, "dry-run ничего не меняет"
    with session_scope(engine) as session:
        stats = unmerge_author(session, client, "A2", SETTINGS, dry_run=False)
        assert stats["works_after"] == {"A1": 1, "A2": 2}
    with session_scope(engine) as session:
        canonical = session.execute(select(Author).where(Author.openalex_id == "A1")).scalar_one()
        duplicate = session.execute(select(Author).where(Author.openalex_id == "A2")).scalar_one()
        assert duplicate.merged_into_id is None
        assert duplicate.is_supervisor_candidate is True
        assert canonical.works_count == 900 and duplicate.works_count == 80, "агрегаты из raw"
        assert {w.openalex_id for w in canonical.works} == {"W1"}
        assert {w.openalex_id for w in duplicate.works} == {"W2", "W3"}
        # идемпотентность: повторный вызов — no-op
        again = unmerge_author(session, client, "A2", SETTINGS, dry_run=False)
        assert again["status"] == "not_merged"


def test_unmerge_refuses_when_canonical_has_other_duplicates(engine: Engine) -> None:
    orcid = "https://orcid.org/0000-0002-1825-0097"
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        for short_id, name, works in (
            ("A1", "T. Aushev", 900),
            ("A2", "Timofey Aushev", 80),
            ("A3", "T. A. Aushev", 10),
        ):
            upsert_author(session, record(short_id, name, orcid, works), inst.id, SETTINGS)
    with session_scope(engine) as session:
        apply_merges(session, find_splits(session).merges)
    with session_scope(engine) as session, pytest.raises(UnmergeError, match="другие дубли"):
        unmerge_author(session, PerAuthorWorksClient({}), "A2", SETTINGS, dry_run=False)


def test_review_file_lists_conflicts_and_near_duplicates() -> None:
    review = [
        MergeGroup(
            "A1",
            ["A2"],
            "name+institution+work, но разные ORCID",
            ["Valery Lukinskiy", "Vladislav Lukinskiy"],
            ["ВШЭ"],
        )
    ]
    near = [
        MergeGroup(
            "A3",
            ["A4"],
            "полное имя ↔ инициалы, один вуз, общих тем 1",
            ["Ilya A. Ryzhikov", "I. A. Ryzhikov"],
            ["МГТУ"],
        )
    ]
    text = render_dedup_review(
        [], [], [], n_suspects=0, n_examples=10, review=review, near_duplicates=near
    )
    assert "## Требуют решения человека — все 1" in text
    assert "разные ORCID" in text and "Lukinskiy" in text
    assert "## Похоже, один человек, но сигнала не хватило — все 1" in text
    assert "Ryzhikov" in text


# ---------------------------------------------------------------------------
# Решения человека о склейках (§4 SPEC_SFR5c): файл dedup_decisions.jsonl.
# Оракулы — те же живые пары, что в правилах #111: Jorstad (два ORCID у одного
# человека, склеить) и Лукинские (общая работа при разных ORCID, не склеивать).
# ---------------------------------------------------------------------------


def decision(
    ids: tuple[str, str], verdict: str, source: str = "#93", note: str = "тест"
) -> DedupDecision:
    return DedupDecision(
        ids=ids, verdict=verdict, by="Борис", date="2026-09-26", source=source, note=note
    )


def _jorstad(session: Session) -> None:
    """Один человек с двумя ORCID — правила его не склеят, решение человека склеит."""
    inst = upsert_institution(session, INSTITUTION_RECORD)
    upsert_author(
        session,
        record("A1", "Svetlana G. Jorstad", "https://orcid.org/0000-0001-6158-1708", 300),
        inst.id,
        SETTINGS,
    )
    upsert_author(
        session,
        record("A2", "S. G. Jorstad", "https://orcid.org/0000-0002-4179-2919", 120),
        inst.id,
        SETTINGS,
    )


def _lukinskiy(session: Session) -> None:
    inst = upsert_institution(session, INSTITUTION_RECORD)
    father = upsert_author(
        session,
        record("A1", "Valery Lukinskiy", "https://orcid.org/0000-0002-2497-8826", 85),
        inst.id,
        SETTINGS,
    )
    son = upsert_author(
        session,
        record("A2", "Vladislav Lukinskiy", "https://orcid.org/0009-0004-4716-3090", 41),
        inst.id,
        SETTINGS,
    )
    upsert_work(session, topical_work("W1", "Logistics"), father.id, since_year=2022)
    upsert_work(session, topical_work("W1", "Logistics"), son.id, since_year=2022)


def test_decision_same_merges_over_two_orcids(engine: Engine) -> None:
    """Jorstad: два разных ORCID блокируют правила, вердикт `same` — склеивает."""
    with session_scope(engine) as session:
        _jorstad(session)
    with session_scope(engine) as session:
        assert find_splits(session).merges == [], "без решения — правила не склеивают"
        findings = find_splits(session, decisions=[decision(("A1", "A2"), "same")])
        assert [g.signal for g in findings.merges] == ["human (#93)"]
        assert findings.merges[0].canonical == "A1", "канонический — тот, у кого больше работ"
        assert findings.review == [], "решённая пара человеку больше не показывается"
        assert [o.status for o in findings.decisions] == [STATUS_MERGED_BY_HUMAN]


def test_decision_different_keeps_lukinskiy_apart_and_out_of_review(engine: Engine) -> None:
    """Лукинские: сигнал есть, но человек сказал «разные» — ни склейки, ни review."""
    with session_scope(engine) as session:
        _lukinskiy(session)
    with session_scope(engine) as session:
        assert len(find_splits(session).review) == 1, "без решения пара висит в review"
        findings = find_splits(session, decisions=[decision(("A1", "A2"), "different", "#108")])
        assert findings.merges == []
        assert findings.review == [], "решение принято — в «требуют решения» пары нет"
        assert findings.near_duplicates == []
        assert findings.namesakes == []
        assert [o.status for o in findings.decisions] == [STATUS_BAN_ACTIVE]


def test_decision_different_blocks_whole_group_transitively(engine: Engine) -> None:
    """Запрещённая пара не сходится и через третий профиль — вся группа к человеку.

    Живой сценарий: третья запись отца («V. Lukinskiy», инициалы, без ORCID)
    делит работы и с отцом, и с сыном — они соавторы. Правила соединили бы всех
    трёх в одну группу, а человек сказал, что двое из них — разные люди.
    """
    with session_scope(engine) as session:
        _lukinskiy(session)
        inst = upsert_institution(session, INSTITUTION_RECORD)
        third = upsert_author(session, record("A3", "V. Lukinskiy", None, 60), inst.id, SETTINGS)
        upsert_work(session, topical_work("W1", "Logistics"), third.id, since_year=2022)
    with session_scope(engine) as session:
        findings = find_splits(session, decisions=[decision(("A1", "A2"), "different", "#108")])
        assert findings.merges == [], "склейка целой группы запрещена"
        assert len(findings.review) == 1
        assert findings.review[0].signal == "запрет человека (#108) + третий профиль"
        assert sorted([findings.review[0].canonical, *findings.review[0].duplicates]) == [
            "A1",
            "A2",
            "A3",
        ]


def test_decision_different_disarms_the_whole_orcid_bucket(engine: Engine) -> None:
    """Один ORCID на трёх, двое из которых — разные люди: склеивать внутри нечего."""
    orcid = "https://orcid.org/0000-0003-0495-6694"
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        upsert_author(session, record("A1", "A. Yu. Kraeva", orcid, 40), inst.id, SETTINGS)
        upsert_author(session, record("A2", "M. A. Kozhin", orcid, 20), inst.id, SETTINGS)
        upsert_author(session, record("A3", "Anna Kraeva", orcid, 30), inst.id, SETTINGS)
    with session_scope(engine) as session:
        findings = find_splits(session, decisions=[decision(("A1", "A2"), "different")])
        assert findings.merges == [], "часть скомпрометированной группы тоже не склеиваем"
        assert findings.review[0].signal == "запрет человека (#93) + один ORCID на группу"


def test_decision_conflict_in_one_group_is_reported_not_swallowed(engine: Engine) -> None:
    """`same` и `different` в одной группе — противоречие, а не тихий выбор одного."""
    with session_scope(engine) as session:
        _lukinskiy(session)
        inst = upsert_institution(session, INSTITUTION_RECORD)
        third = upsert_author(session, record("A3", "V. Lukinskiy", None, 60), inst.id, SETTINGS)
        upsert_work(session, topical_work("W1", "Logistics"), third.id, since_year=2022)
    with session_scope(engine) as session:
        findings = find_splits(
            session,
            decisions=[
                decision(("A1", "A3"), "same", "#93"),
                decision(("A1", "A2"), "different", "#108"),
            ],
        )
        assert findings.merges == []
        assert findings.review[0].signal == (
            "конфликт решений: запрет (#108) и склейка (#93) в одной группе"
        )


def test_decision_with_unknown_id_is_ignored_and_counted(engine: Engine) -> None:
    with session_scope(engine) as session:
        _lukinskiy(session)
    with session_scope(engine) as session:
        findings = find_splits(session, decisions=[decision(("A1", "A999"), "different", "#108")])
        assert len(findings.review) == 1, "чужая строка правил не меняет"
        assert [o.status for o in findings.decisions] == [STATUS_NOT_IN_CATALOGUE]


def test_forbidden_but_merged_is_the_invariant_check(engine: Engine) -> None:
    """Инвариант: запрещённая пара, уже склеенная в БД, — это «не та база»."""
    with session_scope(engine) as session:
        _lukinskiy(session)
    with session_scope(engine) as session:
        # склеиваем «как в sfr5b.db» — до решения человека
        apply_merges(session, [MergeGroup(canonical="A1", duplicates=["A2"], signal="работа")])
    with session_scope(engine) as session:
        findings = find_splits(session, decisions=[decision(("A1", "A2"), "different", "#108")])
        assert [o.status for o in findings.forbidden_but_merged] == [STATUS_FORBIDDEN_BUT_MERGED]
        review = render_dedup_review(
            findings.merges,
            findings.namesakes,
            [],
            review=findings.review,
            near_duplicates=findings.near_duplicates,
            decisions=findings.decisions,
        )
        assert "Инвариант «запрещено, но склеено» — 1" in review
        assert "Пусто — ни одна запрещённая пара не склеена." not in review


def test_applied_merge_recovers_human_signal(engine: Engine) -> None:
    """Старая склейка по решению человека печатается как `human (#93)`, а не «не восстановить»."""
    with session_scope(engine) as session:
        _jorstad(session)
    with session_scope(engine) as session:
        apply_merges(session, [MergeGroup(canonical="A1", duplicates=["A2"], signal="human (#93)")])
    with session_scope(engine) as session:
        findings = find_splits(session, decisions=[decision(("A1", "A2"), "same")])
        assert [g.signal for g in findings.merges] == ["human (#93)"]
        assert [o.status for o in findings.decisions] == [STATUS_ALREADY_MERGED]


def test_review_file_has_human_decisions_section(engine: Engine) -> None:
    with session_scope(engine) as session:
        _lukinskiy(session)
    with session_scope(engine) as session:
        findings = find_splits(session, decisions=[decision(("A1", "A2"), "different", "#108")])
        review = render_dedup_review(
            findings.merges,
            findings.namesakes,
            [],
            review=findings.review,
            near_duplicates=findings.near_duplicates,
            decisions=findings.decisions,
        )
    assert "## Решено человеком — 1" in review
    assert "**different**" in review and "#108" in review
    assert "Борис, 2026-09-26" in review
    assert "Пусто — ни одна запрещённая пара не склеена." in review


def test_default_decisions_path_is_repo_anchored() -> None:
    """Путь по умолчанию не зависит от рабочей директории (ревью SFR-5c)."""
    assert DEFAULT_DECISIONS_PATH.is_absolute()
    assert DEFAULT_DECISIONS_PATH.exists()
    assert DEFAULT_DECISIONS_PATH.parts[-3:] == ("sfr-match", "eval", "dedup_decisions.jsonl")


def test_apply_without_decisions_file_stops(tmp_path: Path) -> None:
    """``--apply`` без файла решений — отказ: склейка необратима, откат ходит в сеть."""
    missing = tmp_path / "нет-такого.jsonl"
    with pytest.raises(DecisionsFileMissing) as exc:
        load_decisions_or_fail(missing, apply=True)
    assert str(missing) in str(exc.value)


def test_dry_run_without_decisions_file_goes_on(tmp_path: Path) -> None:
    """``--dry-run`` без файла работает по одним правилам: ничего не записывается."""
    assert load_decisions_or_fail(tmp_path / "нет-такого.jsonl", apply=False) == []


def test_empty_decisions_file_is_a_valid_state(tmp_path: Path) -> None:
    """Пустой файл — «человек ещё ничего не решал», а не ошибка."""
    empty = tmp_path / "dedup_decisions.jsonl"
    empty.write_text("", encoding="utf-8")
    assert load_decisions_or_fail(empty, apply=True) == []


def test_load_decisions_reads_the_project_file() -> None:
    """Файл в репозитории — актив, а не пример: он обязан читаться как есть."""
    decisions = load_dedup_decisions(DEFAULT_DECISIONS_PATH)
    assert len(decisions) >= 4
    by_key = {d.key: d for d in decisions}
    assert by_key[frozenset(("A5028750791", "A5114375175"))].verdict == "same"  # Jorstad
    assert by_key[frozenset(("A5112269203", "A5073953503"))].verdict == "different"  # Лукинские
    assert all(d.by and d.date and d.source for d in decisions)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (
            '{"ids": ["A1"], "verdict": "same", "by": "б", "date": "д", "source": "#1"}',
            "два разных",
        ),
        (
            '{"ids": ["A1", "A1"], "verdict": "same", "by": "б", "date": "д", "source": "#1"}',
            "два разных",
        ),
        (
            '{"ids": ["A1", "A2"], "verdict": "maybe", "by": "б", "date": "д", "source": "#1"}',
            "verdict",
        ),
        ('{"ids": ["A1", "A2"], "verdict": "same", "by": "б", "date": "д"}', "source"),
        ("{не json", "не JSON"),
    ],
)
def test_load_decisions_rejects_broken_lines(tmp_path: Path, line: str, message: str) -> None:
    path = tmp_path / "decisions.jsonl"
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_dedup_decisions(path)


def test_load_decisions_rejects_two_verdicts_for_one_pair(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        '{"ids": ["A1", "A2"], "verdict": "same", "by": "б", "date": "д", "source": "#1"}\n'
        '{"ids": ["A2", "A1"], "verdict": "different", "by": "б", "date": "д", "source": "#2"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="уже решена выше"):
        load_dedup_decisions(path)


def test_review_file_puts_worst_suspects_first(engine: Engine) -> None:
    """Топ-20 по меньшей группе — приоритет для человека, полный список — справочник."""
    suspects = [
        {
            "author_id": f"A{i:03d}",
            "name": f"Автор {i}",
            "institution": "МФТИ",
            "n_works": 30,
            "cluster_sizes": [20, i],  # меньшая группа растёт с номером
            "topics": ["тема"],
        }
        for i in range(1, 26)
    ]
    text = render_dedup_review([], [], suspects, n_suspects=len(suspects), n_examples=10000)
    assert "### Топ-20 по размеру меньшей тематической группы" in text
    head = text.split("### Полный список")[0]
    # Первым в топе — профиль с самой большой меньшей группой (25), а не A001.
    assert head.index("`A025`") < head.index("`A006`")
    assert "`A001`" not in head, "пять самых слабых в топ-20 не попадают"
    assert "`A001`" in text, "полный список всё равно печатается"


# --- #113: «инициалы-префикс» — третий список человеку, без автосклейки ---


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("S. G. Belogurov", "S. Belogurov", INITIALS_BOTH),
        ("I. Machulin", "I. N. Machulin", INITIALS_BOTH),
        ("Е. Г. Попова", "E. Popova", INITIALS_BOTH),
        ("V. Prosin", "В. В. Просин", INITIALS_BOTH),
        ("Nikita Mkrtchyan", "N. V. Mkrtchyan", INITIALS_ONE_FULL),
        ("Sergey Zelik", "Сергей Витальевич Зелик", INITIALS_ONE_FULL),
        # Тёзки по форме тоже проходят функцию: отсекают их общие темы, а не имя.
        ("A. Bogdanov", "A. A. Bogdanov", INITIALS_BOTH),
    ],
)
def test_initials_prefix_pair_recognises_the_class(left: str, right: str, expected: str) -> None:
    assert initials_prefix_pair(left, right) == expected


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("S. Belogurov", "S. Belogurov"),  # один ключ — это другое правило
        ("A. B. Ivanov", "A. C. Ivanov"),  # инициалы не префикс
        ("S. Belogurov", "S. G. Belousov"),  # разные фамилии
        ("Nikita Mkrtchyan", "Nikolai V. Mkrtchyan"),  # развёрнутые имена спорят
    ],
)
def test_initials_prefix_pair_rejects_others(left: str, right: str) -> None:
    assert initials_prefix_pair(left, right) is None


def test_initials_prefix_pairs_go_to_the_human_and_are_never_merged(engine: Engine) -> None:
    """Machulin-подобная пара — в список; Bogdanov-подобная без общих тем и
    решённая человеком — нет; склеек ни одной (#113)."""
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        authors = {
            short: upsert_author(session, record(short, name, None, works), inst.id, SETTINGS)
            for short, name, works in (
                ("A1", "I. Machulin", 120),
                ("A2", "I. N. Machulin", 15),
                ("A3", "A. Bogdanov", 300),
                ("A4", "A. A. Bogdanov", 20),
                ("A5", "S. G. Belogurov", 16),
                ("A6", "S. Belogurov", 338),
            )
        }
        topics = {
            "A1": ["Neutrino", "Reactors", "Detectors", "Physics"],
            "A2": ["Neutrino", "Reactors", "Detectors", "Math"],
            "A3": ["Biology", "Genetics"],
            "A4": ["Economics", "Law"],
            "A5": ["Neutrino", "Germanium", "Detectors"],
            "A6": ["Neutrino", "Germanium", "Detectors"],
        }
        for short, names in topics.items():
            author_id = authors[short].id
            session.execute(delete(AuthorTopic).where(AuthorTopic.author_id == author_id))
            for score, name in enumerate(reversed(names), start=1):
                session.add(AuthorTopic(author_id=author_id, topic_name=name, score=float(score)))
    belogurov_decided = DedupDecision(
        ids=("A6", "A5"), verdict="same", by="Борис", date="2026-09-26", source="#112"
    )
    with session_scope(engine) as session:
        findings = find_splits(session)
        assert [sorted([g.canonical, *g.duplicates]) for g in findings.initials_prefix] == [
            ["A1", "A2"],
            ["A5", "A6"],
        ]
        assert "общих тем 3" in findings.initials_prefix[0].signal
        assert findings.merges == []
        # Решено человеком — пары в списке больше нет, склейка идёт по решению.
        decided = find_splits(session, decisions=[belogurov_decided])
        assert [sorted([g.canonical, *g.duplicates]) for g in decided.initials_prefix] == [
            ["A1", "A2"]
        ]
        text = render_dedup_review(
            [], [], [], n_suspects=0, initials_prefix=findings.initials_prefix
        )
        assert "## Похоже, один человек — инициалы-префикс — все 2" in text
        assert "`A1`, `A2`" in text


def test_judged_pairs_in_merges_lists_grades_that_a_merge_makes_stale(tmp_path: Path) -> None:
    """#123: оценки на каноническом и на дубле — в список; на постороннем — нет."""
    from sfr_etl.dedup import ROLE_CANONICAL, ROLE_DUPLICATE, judged_pairs_in_merges

    (tmp_path / "judgments.jsonl").write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {"query_id": "q17", "author_id": "A5107886204", "grade": 1},
                {"query_id": "q17", "author_id": "A5104688244", "grade": 2},
                {"query_id": "q01", "author_id": "A0000000001", "grade": 2},
            )
        ),
        encoding="utf-8",
    )
    group = MergeGroup(canonical="A5107886204", duplicates=["A5104688244"], signal="human (#112)")
    found = judged_pairs_in_merges([group], eval_dir=tmp_path)
    assert [(f["author_id"], f["role"]) for f in found] == [
        ("A5107886204", ROLE_CANONICAL),
        ("A5104688244", ROLE_DUPLICATE),
    ]
    text = render_dedup_review([], [], [], n_suspects=0, stale_judgments=found)
    assert "## Оценки, которые склейки делают устаревшими — все 2" in text
