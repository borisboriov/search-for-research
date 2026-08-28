from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select
from test_ingest import INSTITUTION_RECORD, author_record

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Work
from sfr_core.settings import Settings
from sfr_etl.ingest import upsert_author, upsert_institution
from sfr_etl.works import ingest_works_for_author, merge_work_records, upsert_work

SETTINGS = Settings(_env_file=None, openalex_mailto="test@example.com")  # type: ignore[call-arg]


def work_record(
    openalex_id: str = "W1",
    year: int = 2025,
    cited: int = 100,
    abstract: dict[str, Any] | None = None,
    title: str | None = "Quantum widgets at scale",
) -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/{openalex_id}",
        "display_name": title,
        "publication_year": year,
        "cited_by_count": cited,
        "language": "en",
        "topics": [{"display_name": "Quantum Physics", "score": 0.99}],
        "abstract_inverted_index": abstract,
    }


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    db_url = f"sqlite:///{tmp_path}/test.db"
    upgrade_to_head(db_url)
    return make_engine(db_url)


class StubWorksClient:
    """Returns canned pages: first call = cited query, second call = recent query."""

    def __init__(self, cited: list[dict[str, Any]], recent: list[dict[str, Any]]) -> None:
        self.pages = [cited, recent]
        self.calls: list[dict[str, Any]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append(params or {})
        return {"results": self.pages[len(self.calls) - 1]}


def test_merge_prefers_cited_then_recent_capped() -> None:
    cited = [work_record(f"C{i}", cited=1000 - i) for i in range(4)]
    recent = [work_record(f"R{i}", year=2026) for i in range(4)]
    merged = merge_work_records(cited, recent, per_author=4)
    ids = [r["id"].rsplit("/", 1)[-1] for r in merged]
    assert ids == ["C0", "C1", "R0", "R1"]


def test_merge_dedupes_overlap() -> None:
    shared = work_record("W_SHARED")
    merged = merge_work_records([shared], [shared, work_record("R1")], per_author=10)
    ids = [r["id"].rsplit("/", 1)[-1] for r in merged]
    assert ids == ["W_SHARED", "R1"]


def test_merge_tops_up_with_cited_when_few_recent() -> None:
    cited = [work_record(f"C{i}") for i in range(6)]
    merged = merge_work_records(cited, [], per_author=4)
    assert len(merged) == 4


def test_upsert_work_idempotent(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        author = upsert_author(session, author_record(), inst.id, SETTINGS, current_year=2026)
        upsert_work(session, work_record(cited=10), author.id, since_year=2022)
        upsert_work(session, work_record(cited=20), author.id, since_year=2022)
        works = list(session.execute(select(Work)).scalars())
        assert len(works) == 1
        assert works[0].cited_by_count == 20


def test_same_work_allowed_for_two_authors(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        a1 = upsert_author(session, author_record("A1"), inst.id, SETTINGS, current_year=2026)
        a2 = upsert_author(session, author_record("A2"), inst.id, SETTINGS, current_year=2026)
        upsert_work(session, work_record("W_SHARED"), a1.id, since_year=2022)
        upsert_work(session, work_record("W_SHARED"), a2.id, since_year=2022)
        works = list(session.execute(select(Work)).scalars())
        assert len(works) == 2
        assert {w.author_id for w in works} == {a1.id, a2.id}


def test_upsert_work_without_title_skipped(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        author = upsert_author(session, author_record(), inst.id, SETTINGS, current_year=2026)
        assert upsert_work(session, work_record(title=None), author.id, since_year=2022) is None
        assert list(session.execute(select(Work)).scalars()) == []


def test_is_recent_and_abstract(engine: Engine) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        author = upsert_author(session, author_record(), inst.id, SETTINGS, current_year=2026)
        fresh = upsert_work(
            session,
            work_record("W_new", year=2022, abstract={"Hello": [0], "world": [1]}),
            author.id,
            since_year=2022,
        )
        old = upsert_work(session, work_record("W_old", year=2021), author.id, since_year=2022)
        assert fresh is not None and old is not None
        assert fresh.is_recent is True
        assert fresh.abstract_text == "Hello world"
        assert old.is_recent is False
        assert old.abstract_text is None


def test_ingest_works_for_author_queries_and_saves(engine: Engine) -> None:
    cited = [work_record(f"C{i}", year=2015, cited=500) for i in range(3)]
    recent = [work_record(f"R{i}", year=2026, cited=1) for i in range(3)]
    client = StubWorksClient(cited, recent)
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        author = upsert_author(session, author_record(), inst.id, SETTINGS, current_year=2026)
        stats = ingest_works_for_author(
            session,
            client,  # type: ignore[arg-type]
            author,
            since_years=5,
            per_author=4,
            current_year=2026,
        )
        assert stats["saved"] == 4
        # first request: most cited; second: recent-window filter
        assert client.calls[0]["sort"] == "cited_by_count:desc"
        assert "publication_year:>2021" in client.calls[1]["filter"]
        works = list(session.execute(select(Work)).scalars())
        assert len(works) == 4
