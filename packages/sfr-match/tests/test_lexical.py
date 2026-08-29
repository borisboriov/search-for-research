"""BM25 tokenisation: lowercase + punctuation removal, no lemmatisation (SPEC_SFR1 §3.5)."""

from sfr_match.lexical import tokenize


def test_lowercases_and_drops_punctuation() -> None:
    # "и" is dropped by the >= 2 character rule, together with the punctuation.
    assert tokenize("Нейросети, GPU-кластеры и NLP!") == [
        "нейросети",
        "gpu",
        "кластеры",
        "nlp",
    ]


def test_single_character_tokens_are_dropped() -> None:
    assert tokenize("а и в физика") == ["физика"]


def test_digits_are_kept() -> None:
    assert tokenize("Higgs boson at 13 TeV") == ["higgs", "boson", "at", "13", "tev"]


def test_empty_text_yields_no_tokens() -> None:
    assert tokenize("   ...   ") == []
