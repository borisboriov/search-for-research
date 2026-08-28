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
