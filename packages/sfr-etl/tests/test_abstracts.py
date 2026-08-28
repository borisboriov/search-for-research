from sfr_etl.abstracts import reconstruct_abstract


def test_reconstructs_word_order() -> None:
    index = {"deep": [0], "learning": [1, 3], "for": [2], "physics": [4]}
    assert reconstruct_abstract(index) == "deep learning for learning physics"


def test_inverted_index_none() -> None:
    assert reconstruct_abstract(None) is None


def test_inverted_index_empty() -> None:
    assert reconstruct_abstract({}) is None


def test_broken_positions_skipped() -> None:
    index = {
        "good": [0],
        "bad-not-list": "oops",
        "bad-entries": [None, "x", -5, True],
        "fine": [1],
    }
    assert reconstruct_abstract(index) == "good fine"


def test_all_broken_returns_none() -> None:
    assert reconstruct_abstract({"a": "nope", "b": [-1]}) is None


def test_unicode_preserved() -> None:
    index = {"Квантовая": [0], "запутанность": [1]}
    assert reconstruct_abstract(index) == "Квантовая запутанность"
