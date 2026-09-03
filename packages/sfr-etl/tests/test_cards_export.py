"""`sfr export cards` — card enrichment for the API (SFR-3 §4)."""

import json
from pathlib import Path

import pytest
from sqlalchemy import Engine
from test_profiles_export import SETTINGS, seed

from sfr_core.db import make_engine, session_scope, upgrade_to_head
from sfr_etl.export import export_cards_jsonl
from sfr_etl.profiles import build_profiles


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    db_url = f"sqlite:///{tmp_path}/test.db"
    upgrade_to_head(db_url)
    return make_engine(db_url)


def export_from(engine: Engine, tmp_path: Path) -> list[dict[str, object]]:
    seed(engine)
    with session_scope(engine) as session:
        build_profiles(session, SETTINGS)
        out = tmp_path / "cards.jsonl"
        n = export_cards_jsonl(session, out)
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert n == len(lines)
    return lines


def test_one_card_per_supervisor_profile(engine: Engine, tmp_path: Path) -> None:
    cards = export_from(engine, tmp_path)
    assert len(cards) == 3  # the weak author has no profile and no card
    assert all(card["id"].startswith("A") for card in cards)


def test_card_carries_citations_and_top_works(engine: Engine, tmp_path: Path) -> None:
    card = export_from(engine, tmp_path)[0]
    assert isinstance(card["cited_by_count"], int)
    works = card["top_works"]
    assert 1 <= len(works) <= 10
    assert {"title", "year"} <= set(works[0])


def test_position_and_email_are_declared_but_empty(engine: Engine, tmp_path: Path) -> None:
    """No such data in the catalogue and nothing new is parsed (SPEC_SFR3 §4)."""
    for card in export_from(engine, tmp_path):
        assert card["position"] is None
        assert card["email"] is None
