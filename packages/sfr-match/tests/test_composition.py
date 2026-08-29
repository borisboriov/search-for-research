"""What goes into the index: the three compositions (SPEC_SFR2 §5)."""

import json
from pathlib import Path

from sfr_core.schemas import ProfileExport, WorkExport
from sfr_match.composition import COMPOSITIONS, compose_indexed_text
from sfr_match.profiles import load_profiles

EXPORT = ProfileExport(
    id="A1",
    name="A. Author",
    institution="МФТИ",
    h_index=7,
    works_count=120,
    topics=["Neutrino Physics", "Dark Matter"],
    profile_text=(
        "A. Author — МФТИ. h-index: 7.\n"
        "Ключевые темы: Neutrino Physics; Dark Matter.\n"
        "«Search for 0νββ» (2024). We report a search for neutrinoless double beta decay…"
    ),
    works=[
        WorkExport(
            openalex_id="W1", title="Search for 0νββ", publication_year=2024, cited_by_count=90
        ),
        WorkExport(
            openalex_id="W2", title="Dark matter detector", publication_year=2020, cited_by_count=5
        ),
    ],
)


def test_full_is_the_profile_text_verbatim() -> None:
    assert compose_indexed_text(EXPORT, "full") == EXPORT.profile_text


def test_topics_keeps_the_header_and_the_topics_line_only() -> None:
    text = compose_indexed_text(EXPORT, "topics")
    assert text == "A. Author — МФТИ. h-index: 7.\nКлючевые темы: Neutrino Physics; Dark Matter."
    assert "0νββ" not in text


def test_topics_titles_adds_titles_but_no_abstract_fragments() -> None:
    text = compose_indexed_text(EXPORT, "topics_titles")
    assert "«Search for 0νββ» (2024)." in text
    assert "«Dark matter detector» (2020)." in text
    assert "We report a search" not in text


def test_every_composition_is_shorter_than_or_equal_to_the_baseline() -> None:
    lengths = {mode: len(compose_indexed_text(EXPORT, mode)) for mode in COMPOSITIONS}
    assert lengths["topics"] < lengths["topics_titles"] <= lengths["full"]


def test_a_profile_without_topics_or_works_is_just_its_header() -> None:
    bare = EXPORT.model_copy(update={"topics": [], "works": []})
    assert compose_indexed_text(bare, "topics_titles") == "A. Author — МФТИ. h-index: 7."


def test_titles_stop_at_the_length_ceiling() -> None:
    many = EXPORT.model_copy(
        update={
            "works": [
                WorkExport(openalex_id=f"W{i}", title="Очень длинное название работы " * 10)
                for i in range(20)
            ]
        }
    )
    assert len(compose_indexed_text(many, "topics_titles")) <= 1500


def test_load_profiles_indexes_the_composition_but_shows_the_full_card(tmp_path: Path) -> None:
    path = tmp_path / "profiles.jsonl"
    path.write_text(EXPORT.model_dump_json() + "\n", encoding="utf-8")
    record = load_profiles(path, clean=True, compose="topics")[0]
    assert "0νββ" not in record.indexed_text
    assert record.profile_text == EXPORT.profile_text  # the export is never rewritten
    assert "0νββ" in record.display_text  # the card keeps the whole profile
    assert record.works_count == 120


def test_profiles_without_works_count_still_load(tmp_path: Path) -> None:
    """SFR-0 exports predate the field; they must keep working."""
    path = tmp_path / "profiles.jsonl"
    payload = json.loads(EXPORT.model_dump_json())
    payload.pop("works_count")
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    assert load_profiles(path)[0].works_count is None
