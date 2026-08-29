"""Per-model preprocessing: asymmetric models must get their prefixes (SPEC_SFR1 §3.1)."""

import pytest

from sfr_match.models import DEFAULT_MODELS, REGISTRY, resolve_model


def test_e5_uses_query_and_passage_prefixes() -> None:
    spec = resolve_model("e5-base")
    assert spec.prepare_query("нейросети") == "query: нейросети"
    assert spec.prepare_document("профиль") == "passage: профиль"


def test_frida_uses_search_prefixes() -> None:
    spec = resolve_model("frida")
    assert spec.prepare_query("нейросети") == "search_query: нейросети"
    assert spec.prepare_document("профиль") == "search_document: профиль"


def test_symmetric_models_get_no_prefix() -> None:
    for key in ("mpnet", "minilm"):
        spec = resolve_model(key)
        assert spec.prepare_query("x") == "x"
        assert spec.prepare_document("x") == "x"


def test_resolve_by_huggingface_id() -> None:
    assert resolve_model("intfloat/multilingual-e5-base").key == "e5-base"


def test_unknown_model_raises_with_the_known_keys() -> None:
    with pytest.raises(KeyError, match="e5-base"):
        resolve_model("no-such-model")


def test_slug_marks_the_clean_variant() -> None:
    spec = resolve_model("e5-base")
    assert spec.slug(clean=False) == "e5-base"
    assert spec.slug(clean=True) == "e5-base_clean"


def test_all_default_variants_are_registered() -> None:
    assert set(DEFAULT_MODELS) == set(REGISTRY)
