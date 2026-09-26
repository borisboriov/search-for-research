"""Дедупликация авторов (SPEC_SFR5 §3): склейка расщеплённых и флаг чужой склейки."""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, delete, select
from test_ingest import INSTITUTION_RECORD, author_record
from test_works import work_record

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Author, AuthorTopic, Work
from sfr_core.settings import Settings
from sfr_etl.dedup import (
    MergeGroup,
    UnmergeError,
    apply_merges,
    detect_suspect_merges,
    find_splits,
    first_names_conflict,
    is_abbreviation_pair,
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
