from pathlib import Path

from sqlalchemy import inspect, select

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_core.models import Author, Institution


def test_migrations_create_all_tables(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/test.db"
    upgrade_to_head(db_url)
    engine = make_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    assert {
        "institutions",
        "authors",
        "works",
        "author_topics",
        "supervisor_profiles",
    } <= tables


def test_upgrade_is_idempotent(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/test.db"
    upgrade_to_head(db_url)
    upgrade_to_head(db_url)  # second run must be a no-op, not an error


def test_models_roundtrip(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/test.db"
    upgrade_to_head(db_url)
    engine = make_engine(db_url)
    with session_scope(engine) as session:
        inst = Institution(openalex_id="I153845743", name_en="MIPT", country="RU")
        session.add(inst)
        session.flush()
        session.add(
            Author(
                openalex_id="A1",
                display_name="Test Author",
                last_known_institution_id=inst.id,
                works_count=12,
                h_index=7,
                raw={"id": "A1"},
            )
        )
    with session_scope(engine) as session:
        author = session.execute(select(Author)).scalar_one()
        assert author.institution is not None
        assert author.institution.name_en == "MIPT"
        assert author.raw == {"id": "A1"}
        assert author.is_supervisor_candidate is False
