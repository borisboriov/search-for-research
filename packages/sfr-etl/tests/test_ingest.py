from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Author, AuthorTopic, Institution
from sfr_core.settings import Settings
from sfr_etl.ingest import (
    extract_cyrillic_name,
    ingest_authors,
    last_publication_year,
    short_id,
    upsert_author,
    upsert_institution,
)

SETTINGS = Settings(_env_file=None, openalex_mailto="test@example.com")  # type: ignore[call-arg]

INSTITUTION_RECORD = {
    "id": "https://openalex.org/I153845743",
    "ror": "https://ror.org/00v0z9322",
    "display_name": "Moscow Institute of Physics and Technology",
    "display_name_alternatives": [
        "Moscow Institute of Physics and Technology",
        "Московский физико-технический институт",
    ],
    "country_code": "RU",
}


def author_record(
    openalex_id: str = "A1",
    works_count: int = 50,
    h_index: int = 12,
    last_year: int = 2026,
    topics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/{openalex_id}",
        "orcid": "https://orcid.org/0000-0000-0000-0001",
        "display_name": "Иван Петров",
        "works_count": works_count,
        "cited_by_count": 1000,
        "summary_stats": {"h_index": h_index, "i10_index": 20},
        "counts_by_year": [
            {"year": 2019, "works_count": 3},
            {"year": last_year, "works_count": 1},
            {"year": 2018, "works_count": 0},
        ],
        "topics": topics
        if topics is not None
        else [
            {"display_name": "Machine Learning", "count": 30},
            {"display_name": "Optics", "count": 10},
        ],
    }


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    db_url = f"sqlite:///{tmp_path}/test.db"
    upgrade_to_head(db_url)
    return make_engine(db_url)


class StubClient:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    def paginate(self, path: str, params: Any = None, **kwargs: Any) -> Iterator[dict[str, Any]]:
        max_records = kwargs.get("max_records")
        yield from self.records[:max_records]


def test_short_id() -> None:
    assert short_id("https://openalex.org/A123") == "A123"
    assert short_id("A123") == "A123"


def test_extract_cyrillic_name() -> None:
    assert extract_cyrillic_name(["MIPT", "Московский физтех"]) == "Московский физтех"
    assert extract_cyrillic_name(["MIPT only"]) is None
    assert extract_cyrillic_name([]) is None


def test_last_publication_year_ignores_zero_and_order() -> None:
    counts = [
        {"year": 2026, "works_count": 0},
        {"year": 2020, "works_count": 2},
        {"year": 2024, "works_count": 1},
    ]
    assert last_publication_year(counts) == 2024
    assert last_publication_year([]) is None
    assert last_publication_year([{"year": 2026, "works_count": 0}]) is None


def test_upsert_institution_idempotent(engine: Engine) -> None:
    with session_scope(engine) as session:
        upsert_institution(session, INSTITUTION_RECORD)
        upsert_institution(session, INSTITUTION_RECORD)
        institutions = list(session.execute(select(Institution)).scalars())
        assert len(institutions) == 1
        inst = institutions[0]
        assert inst.openalex_id == "I153845743"
        assert inst.name_ru == "Московский физико-технический институт"
        assert inst.country == "RU"


def test_upsert_author_idempotent_and_updates(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        upsert_author(session, author_record(works_count=50), inst.id, SETTINGS, current_year=2026)
        upsert_author(session, author_record(works_count=99), inst.id, SETTINGS, current_year=2026)
        authors = list(session.execute(select(Author)).scalars())
        assert len(authors) == 1
        assert authors[0].works_count == 99
        assert authors[0].h_index == 12
        assert authors[0].raw is not None and authors[0].raw["works_count"] == 99


def test_upsert_author_applies_heuristic(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        good = upsert_author(session, author_record("A1"), inst.id, SETTINGS, current_year=2026)
        stale = upsert_author(
            session, author_record("A2", last_year=2022), inst.id, SETTINGS, current_year=2026
        )
        weak = upsert_author(
            session, author_record("A3", h_index=2), inst.id, SETTINGS, current_year=2026
        )
        assert good.is_supervisor_candidate is True
        # rejected authors are kept with flag=False, not deleted
        assert stale.is_supervisor_candidate is False
        assert weak.is_supervisor_candidate is False


def test_author_topics_replaced_not_duplicated(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        upsert_author(session, author_record(), inst.id, SETTINGS, current_year=2026)
        upsert_author(
            session,
            author_record(topics=[{"display_name": "Quantum Computing", "count": 5}]),
            inst.id,
            SETTINGS,
            current_year=2026,
        )
        topics = list(session.execute(select(AuthorTopic)).scalars())
        assert [t.topic_name for t in topics] == ["Quantum Computing"]
        assert topics[0].score == 5.0


def test_ingest_authors_end_to_end(engine: Engine) -> None:
    records = [author_record(f"A{i}", h_index=1 if i % 2 else 10) for i in range(4)]
    client = StubClient(records)
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        stats = ingest_authors(session, client, inst, SETTINGS, max_authors=3)  # type: ignore[arg-type]
        assert stats["total"] == 3
        assert stats["candidates"] == 2  # A0, A2 have h_index=10
        assert len(list(session.execute(select(Author)).scalars())) == 3
