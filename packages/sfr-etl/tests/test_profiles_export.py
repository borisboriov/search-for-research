import json
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from test_ingest import INSTITUTION_RECORD, author_record
from test_works import work_record

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import SupervisorProfile
from sfr_core.settings import Settings
from sfr_etl.export import export_profiles_jsonl
from sfr_etl.ingest import upsert_author, upsert_institution
from sfr_etl.profiles import build_profiles
from sfr_etl.report import compute_stats, render_report, sample_profiles
from sfr_etl.works import upsert_work

SETTINGS = Settings(_env_file=None, openalex_mailto="test@example.com")  # type: ignore[call-arg]

ABSTRACT = {str(i): [i] for i in range(120)}  # 120 numbered "words"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    db_url = f"sqlite:///{tmp_path}/test.db"
    upgrade_to_head(db_url)
    return make_engine(db_url)


def seed(engine: Engine, n_candidates: int = 3) -> None:
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        for i in range(n_candidates):
            author = upsert_author(
                session, author_record(f"A{i}"), inst.id, SETTINGS, current_year=2026
            )
            for j in range(6):
                upsert_work(
                    session,
                    work_record(f"W{i}_{j}", year=2020 + j, cited=j * 10, abstract=ABSTRACT),
                    author.id,
                    since_year=2022,
                )
        # non-candidate: must not get a profile
        upsert_author(
            session, author_record("A_weak", h_index=1), inst.id, SETTINGS, current_year=2026
        )


def test_build_profiles_only_for_candidates(engine: Engine) -> None:
    seed(engine)
    with session_scope(engine) as session:
        stats = build_profiles(session, SETTINGS)
        assert stats["profiles"] == 3
        profiles = list(session.execute(select(SupervisorProfile)).scalars())
        assert len(profiles) == 3
        for p in profiles:
            assert p.n_works == 6
            assert p.n_abstracts == 6
            assert "Иван Петров" in p.profile_text


def test_build_profiles_idempotent(engine: Engine) -> None:
    seed(engine)
    with session_scope(engine) as session:
        build_profiles(session, SETTINGS)
        build_profiles(session, SETTINGS)
        assert len(list(session.execute(select(SupervisorProfile)).scalars())) == 3


def test_export_jsonl_valid_lines(engine: Engine, tmp_path: Path) -> None:
    seed(engine)
    out = tmp_path / "exports" / "profiles.jsonl"
    with session_scope(engine) as session:
        build_profiles(session, SETTINGS)
        n = export_profiles_jsonl(session, out)
    assert n == 3
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    for line in lines:
        record = json.loads(line)
        assert set(record) == {
            "id",
            "name",
            "institution",
            "h_index",
            "topics",
            "profile_text",
            "works",
        }
        assert record["institution"] == "Московский физико-технический институт"
        assert len(record["works"]) == 6
        assert record["works"][0]["has_abstract"] is True


def test_report_stats_and_render(engine: Engine) -> None:
    seed(engine)
    with session_scope(engine) as session:
        build_profiles(session, SETTINGS)
        stats = compute_stats(session)
        samples = sample_profiles(session)
    assert stats["n_authors"] == 4
    assert stats["n_candidates"] == 3
    assert stats["n_works"] == 18
    assert stats["n_works_with_abstract"] == 18
    assert stats["n_profiles"] == 3
    assert len(stats["top_topics"]) >= 1
    # all three candidates share the same display_name in the fixture
    assert stats["duplicate_candidate_names"] == ["Иван Петров"]
    markdown = render_report(stats, samples, {"etl authors": {"seconds": 1}}, 10, 1.5)
    assert "# REPORT" in markdown
    assert "Иван Петров" in markdown
    assert "Топ-15 тем" in markdown
