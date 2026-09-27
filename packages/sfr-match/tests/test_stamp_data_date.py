"""Дата данных каталога в meta.json индекса (#16): расчёт по БД и штамп."""

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sfr_core.models import Author, Base
from sfr_match.index import META_FILE, IndexMeta, load_meta, stamp_data_updated_at

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.fixture(scope="module")
def sd():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("stamp_data_date", SCRIPTS / "stamp_data_date.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _meta(**extra: object) -> dict[str, object]:
    meta = IndexMeta(
        model_key="frida",
        hf_id=None,
        kind="dense",
        clean=True,
        n_profiles=2,
        dim=4,
        build_seconds=1.0,
        built_at="2026-09-26T18:09:55+00:00",
        corpus_sha="35e591d4",
    )
    return {**asdict(meta), **extra}


def test_latest_update_takes_the_freshest_date_and_ignores_gaps(sd) -> None:  # type: ignore[no-untyped-def]
    raws = [
        {"updated_date": "2026-09-04T12:18:09.1"},
        {"updated_date": "2026-07-16T12:16:06"},
        None,
        {},
        {"updated_date": None},
    ]
    assert sd.latest_update(raws) == "2026-09-04"
    assert sd.latest_update([None, {}]) is None


def test_catalogue_date_counts_only_live_candidates(sd) -> None:  # type: ignore[no-untyped-def]
    # Выбывшие в склейку и не-кандидаты в НР на дату каталога не влияют.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        live = Author(
            openalex_id="A1",
            display_name="a",
            is_supervisor_candidate=True,
            raw={"updated_date": "2026-09-04T00:00:00"},
        )
        session.add(live)
        session.flush()
        session.add_all(
            [
                Author(
                    openalex_id="A2",
                    display_name="b",
                    is_supervisor_candidate=True,
                    merged_into_id=live.id,
                    raw={"updated_date": "2026-09-20T00:00:00"},
                ),
                Author(
                    openalex_id="A3",
                    display_name="c",
                    is_supervisor_candidate=False,
                    raw={"updated_date": "2026-09-21T00:00:00"},
                ),
            ]
        )
        session.commit()
        assert sd.catalogue_data_date(session) == "2026-09-04"


def test_stamp_keeps_everything_else_and_old_meta_still_loads(tmp_path: Path) -> None:
    (tmp_path / META_FILE).write_text(json.dumps(_meta()), encoding="utf-8")
    assert load_meta(tmp_path).data_updated_at == ""  # старый meta.json без поля
    before = load_meta(tmp_path)
    after = stamp_data_updated_at(tmp_path, "2026-09-04")
    assert after.data_updated_at == "2026-09-04"
    assert after.version == before.version
    assert after.built_at == before.built_at
    assert load_meta(tmp_path).data_updated_at == "2026-09-04"
