"""Признаки смеси двух людей в профиле (#119): оракулы в обе стороны."""

from typing import Any

from sqlalchemy import Engine, select
from test_dedup import SETTINGS, engine, record  # noqa: F401 — фикстура engine
from test_ingest import INSTITUTION_RECORD

from sfr_core.db import session_scope
from sfr_core.models import Author, Institution, Work
from sfr_etl.dedup import (
    MIX_AFFILIATIONS,
    MIX_MARGINAL,
    MIX_TOPIC_DOMAINS,
    MIX_WORK_DOMAINS,
    detect_suspect_merges,
    mix_candidates,
    mix_signals,
    render_dedup_review,
)
from sfr_etl.ingest import upsert_author, upsert_institution

DOMAINS = {
    "Physics and Astronomy": "Physical Sciences",
    "Engineering": "Physical Sciences",
    "Medicine": "Health Sciences",
}


def _author(raw: dict[str, Any], institution: str = "I1") -> Author:
    author = Author(openalex_id="A1", display_name="Test Author", raw=raw)
    author.institution = Institution(openalex_id=institution, name_en="Uni")
    return author


def _works(fields: list[str | None]) -> list[Work]:
    return [
        Work(openalex_id=f"W{i}", title="t", topics=[{"field": f, "subfield": "Same"}] if f else [])
        for i, f in enumerate(fields)
    ]


def _names(signals: list[tuple[str, str]]) -> list[str]:
    return [name for name, _ in signals]


def test_hundred_organisations_flags_ninety_nine_does_not() -> None:
    many = _author({"affiliations": [{"institution": {"id": f"I{i}"}} for i in range(100)]})
    fewer = _author({"affiliations": [{"institution": {"id": f"I{i}"}} for i in range(99)]})
    assert MIX_AFFILIATIONS in _names(mix_signals(many, []))
    assert mix_signals(fewer, []) == []


def test_catalogue_institution_as_a_marginal_affiliation() -> None:
    def author(years_here: list[int], years_elsewhere: list[int]) -> Author:
        return _author(
            {
                "affiliations": [
                    {"institution": {"id": "https://openalex.org/I1"}, "years": years_here},
                    {"institution": {"id": "https://openalex.org/I9"}, "years": years_elsewhere},
                ]
            }
        )

    # Shestakov A: 1 год МФТИ из 17 лет аффилиаций — вуз каталога случайный.
    assert MIX_MARGINAL in _names(mix_signals(author([2023], list(range(2006, 2024))), []))
    # Пять лет из двадцати — настоящая аффилиация, не случайная.
    assert mix_signals(author([2020, 2021, 2022, 2023, 2024], list(range(2005, 2025))), []) == []
    # Короткая карьера (срок меньше 15 лет) — судить не по чему.
    assert mix_signals(author([2024], list(range(2015, 2025))), []) == []


def test_topic_domains_split() -> None:
    def author(life: int, physical: int) -> Author:
        return _author(
            {
                "topics": [
                    {"count": life, "domain": {"display_name": "Life Sciences"}},
                    {"count": physical, "domain": {"display_name": "Physical Sciences"}},
                ]
            }
        )

    assert MIX_TOPIC_DOMAINS in _names(mix_signals(author(58, 42), []))  # Hossain A
    assert mix_signals(author(70, 30), []) == []


def test_work_domains_split_and_unknown_field_is_not_a_second_domain() -> None:
    mixed = _works(["Engineering"] * 6 + ["Medicine"] * 4)
    signals = mix_signals(_author({}), mixed, domains=DOMAINS)
    assert MIX_WORK_DOMAINS in _names(signals)
    assert "4 из 10" in dict(signals)[MIX_WORK_DOMAINS]
    # Три медицинские из десяти — меньше порога: междисциплинарность, не смесь.
    assert (
        mix_signals(_author({}), _works(["Engineering"] * 7 + ["Medicine"] * 3), domains=DOMAINS)
        == []
    )
    # Работы без области (записи до SFR-5) — пропуск, а не второй домен.
    unknown = _works(["Engineering"] * 6 + [None] * 4)
    assert mix_signals(_author({}), unknown, domains=DOMAINS) == []


def test_mix_candidates_only_reads(engine: Engine) -> None:  # noqa: F811
    """--dry-run считает признаки через mix_candidates — флаг в БД не меняется."""
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        author = upsert_author(session, record("A1", "Jianmin Wu", None, 1445), inst.id, SETTINGS)
        author.raw = {
            **(author.raw or {}),
            "affiliations": [{"institution": {"id": f"I{i}"}} for i in range(526)],
        }
    with session_scope(engine) as session:
        found, counts = mix_candidates(session)
        assert [item["author_id"] for item in found] == ["A1"]
        assert counts[MIX_AFFILIATIONS] == 1
        assert not session.dirty and not session.new
        stored = session.execute(select(Author.suspect_merge)).scalar_one()
        assert stored is False


def test_new_signals_do_not_set_the_flag(engine: Engine) -> None:  # noqa: F811
    """#119 — замер, а не смена детектора: флаг ставит только «две группы тем»."""
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        author = upsert_author(session, record("A1", "Jianmin Wu", None, 1445), inst.id, SETTINGS)
        author.raw = {
            **(author.raw or {}),
            "affiliations": [{"institution": {"id": f"I{i}"}} for i in range(526)],
        }
    with session_scope(engine) as session:
        found, _ = mix_candidates(session)
        assert [item["author_id"] for item in found] == ["A1"], "признак есть"
        stats = detect_suspect_merges(session)
        assert stats["suspect"] == 0
        text = render_dedup_review([], [], [], n_suspects=0, mix=found)
    with session_scope(engine) as session:
        assert session.execute(select(Author.suspect_merge)).scalar_one() is False
    assert "## Признаки смеси двух людей (#119) — топ-1 из 1, только для просмотра" in text
    assert "**Флаг `suspect_merge` они не ставят**" in text
    assert "организаций" in text.split("## Признаки смеси")[1]
