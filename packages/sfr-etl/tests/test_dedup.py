"""Дедупликация авторов (SPEC_SFR5 §3): склейка расщеплённых и флаг чужой склейки."""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select
from test_ingest import INSTITUTION_RECORD, author_record
from test_works import work_record

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Author, AuthorTopic, Work
from sfr_core.settings import Settings
from sfr_etl.dedup import (
    apply_merges,
    detect_suspect_merges,
    find_splits,
    is_abbreviation_pair,
    name_key,
    normalize_orcid,
    render_dedup_review,
    suspect_examples,
)
from sfr_etl.ingest import upsert_author, upsert_institution
from sfr_etl.works import upsert_work

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
        assert [g.signal for g in merges] == ["склеено ранее"]
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
