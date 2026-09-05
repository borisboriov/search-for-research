from sfr_core.profile import WorkForProfile, build_profile_text, select_works_for_profile


def work(
    title: str = "Deep learning for physics",
    year: int | None = 2025,
    cited: int = 10,
    abstract: str | None = "We study deep learning methods applied to particle physics data. " * 10,
) -> WorkForProfile:
    return WorkForProfile(
        title=title, publication_year=year, cited_by_count=cited, abstract_text=abstract
    )


def build(**kwargs: object) -> str:
    defaults: dict[str, object] = {
        "name": "Иван Петров",
        "institution_name": "Московский физико-технический институт",
        "topics": ["Machine Learning", "Particle Physics"],
        "works": [work(f"Work {i}", cited=i) for i in range(8)],
        "h_index": 20,
    }
    defaults.update(kwargs)
    return build_profile_text(**defaults)  # type: ignore[arg-type]


def test_profile_within_bounds() -> None:
    text = build()
    assert 300 <= len(text) <= 1500


def test_profile_contains_name_affiliation_topics_titles() -> None:
    text = build()
    assert "Иван Петров" in text
    assert "Московский физико-технический институт" in text
    assert "Machine Learning" in text
    assert "Work" in text  # work titles present


def test_profile_without_abstracts_still_builds() -> None:
    works = [work(f"Работа о квантовых вычислениях номер {i}", abstract=None) for i in range(10)]
    text = build(works=works)
    assert "Работа о квантовых вычислениях" in text
    assert len(text) <= 1500


def test_profile_no_works_no_topics_short_but_valid() -> None:
    text = build(works=[], topics=[], h_index=None)
    assert text.startswith("Иван Петров")
    assert len(text) < 300  # nothing to say — completeness is tracked by the caller


def test_profile_max_length_respected_with_long_abstracts() -> None:
    long_abstract = "Очень длинный абстракт про машинное обучение и физику частиц. " * 100
    works = [work(f"Работа {i}", abstract=long_abstract) for i in range(10)]
    text = build(works=works)
    assert len(text) <= 1500


def test_short_profile_extended_from_abstract() -> None:
    # single work, abstract much longer than the default fragment
    works = [work("Одна работа", abstract="слово " * 200)]
    text = build(works=works, topics=[], h_index=None)
    assert len(text) >= 300


def test_overshoot_cut_at_word_boundary() -> None:
    # forces the extension pass to overshoot a tight max_chars
    works = [work("Одна работа", abstract="длинноеслово " * 100)]
    text = build_profile_text(
        name="Иван Петров",
        institution_name=None,
        topics=[],
        works=works,
        min_chars=400,
        max_chars=420,
    )
    assert len(text) <= 420
    assert not text.endswith("длинноесл")  # no mid-word cut
    assert text.endswith("…")


def test_source_language_preserved() -> None:
    works = [work("Квантовая запутанность в фотонных системах", abstract="Мы исследуем " * 30)]
    text = build(works=works)
    assert "Квантовая запутанность в фотонных системах" in text
    assert "Мы исследуем" in text


def test_select_works_prefers_cited_then_recent() -> None:
    works = [
        WorkForProfile("old-cited", 2010, 5000, None),
        WorkForProfile("new-uncited", 2026, 0, None),
        WorkForProfile("mid", 2020, 100, None),
    ]
    selected = select_works_for_profile(works, max_works=2)
    assert selected[0].title == "old-cited"
    assert selected[1].title == "new-uncited"


def test_mega_collaboration_works_fill_only_leftover_slots() -> None:
    """SFR-5: статьи коллабораций цитируются на порядки чаще личных работ и,
    попав в profile_text, делают профили всех участников одинаковыми."""
    mega = [
        WorkForProfile(
            title=f"Observation of the Higgs boson, part {i}",
            publication_year=2025,
            cited_by_count=10_000 + i,
            abstract_text=None,
            is_mega_collaboration=True,
        )
        for i in range(12)
    ]
    own = [
        WorkForProfile(
            title=f"Silicon detector calibration {i}",
            publication_year=2020 + i,
            cited_by_count=5,
            abstract_text=None,
        )
        for i in range(4)
    ]
    selected = select_works_for_profile(mega + own)
    assert [w.title for w in selected[:4]] == [w.title for w in own]
    assert all(w.is_mega_collaboration for w in selected[4:])


def test_profile_without_works_uses_more_topics() -> None:
    """Профиль без загруженных работ держится на темах — их берётся больше."""
    topics = [f"Тема {i}" for i in range(20)]
    text = build_profile_text(name="X", institution_name="Y", topics=topics, works=[])
    assert "Тема 19" in text
    with_works = build_profile_text(
        name="X",
        institution_name="Y",
        topics=topics,
        works=[WorkForProfile("T", 2025, 1, "a" * 400)],
    )
    assert "Тема 19" not in with_works
