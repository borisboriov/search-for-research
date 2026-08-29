"""Index building and search, driven by the fake embedder (no model downloads)."""

import json
from pathlib import Path

import pytest

from sfr_match.evalset import Query
from sfr_match.evaluate import build_pool, load_run, run_queries, save_run
from sfr_match.index import build_index, index_path, load_meta
from sfr_match.models import resolve_model
from sfr_match.profiles import ProfileRecord, load_profiles
from sfr_match.search import Bm25Backend, DenseBackend


def _build(tmp_path, profiles, key, fake_embedder, clean=False):  # type: ignore[no-untyped-def]
    spec = resolve_model(key)
    out_dir = index_path(spec, clean=clean, root=tmp_path)
    embedder = fake_embedder(spec)
    meta = build_index(profiles, spec, clean=clean, out_dir=out_dir, embedder=embedder)
    return spec, out_dir, meta, embedder


def test_dense_index_writes_meta_docs_and_vectors(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    _, out_dir, meta, _ = _build(tmp_path, profiles, "e5-base", fake_embedder)
    assert meta.n_profiles == 3
    assert meta.dim == 64
    assert (out_dir / "index.faiss").exists()
    assert load_meta(out_dir).model_key == "e5-base"
    docs = json.loads((out_dir / "docs.json").read_text(encoding="utf-8"))
    assert [doc["id"] for doc in docs] == ["A1", "A2", "A3"]


def test_documents_are_embedded_with_the_passage_prefix(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    _, _, _, embedder = _build(tmp_path, profiles, "e5-base", fake_embedder)
    assert all(text.startswith("passage: ") and not is_query for text, is_query in embedder.seen)


def test_dense_search_ranks_the_matching_profile_first(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    spec, out_dir, _, _ = _build(tmp_path, profiles, "e5-base", fake_embedder)
    backend = DenseBackend(out_dir, spec, embedder=fake_embedder(spec))
    hits = backend.search("сверхпроводимость купратов", k=3)
    assert hits[0].author_id == "A2"
    assert [hit.rank for hit in hits] == [1, 2, 3]
    assert hits[0].score >= hits[1].score >= hits[2].score


def test_dense_search_embeds_the_query_with_the_query_prefix(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    spec, out_dir, _, _ = _build(tmp_path, profiles, "e5-base", fake_embedder)
    embedder = fake_embedder(spec)
    DenseBackend(out_dir, spec, embedder=embedder).search("нейросети", k=1)
    assert embedder.seen == [("query: нейросети", True)]


def test_search_caps_k_at_the_corpus_size(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    spec, out_dir, _, _ = _build(tmp_path, profiles, "e5-base", fake_embedder)
    backend = DenseBackend(out_dir, spec, embedder=fake_embedder(spec))
    assert len(backend.search("что угодно", k=50)) == 3


def test_bm25_index_needs_no_vectors_and_finds_lexical_matches(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    spec, out_dir, meta, _ = _build(tmp_path, profiles, "bm25", fake_embedder)
    assert meta.dim is None
    assert not (out_dir / "index.faiss").exists()
    hits = Bm25Backend(out_dir, spec).search("vehicle routing logistics", k=3)
    assert hits[0].author_id == "A3"


def test_missing_index_directory_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="sfr-match index"):
        load_meta(tmp_path / "nothing")


def test_clean_variant_lands_in_its_own_directory(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    _, raw_dir, _, _ = _build(tmp_path, profiles, "e5-base", fake_embedder, clean=False)
    _, clean_dir, meta, _ = _build(tmp_path, profiles, "e5-base", fake_embedder, clean=True)
    assert raw_dir != clean_dir
    assert clean_dir.name.endswith("_clean")
    assert meta.clean is True


def test_run_and_pool_round_trip(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    spec, out_dir, _, _ = _build(tmp_path, profiles, "e5-base", fake_embedder)
    backend = DenseBackend(out_dir, spec, embedder=fake_embedder(spec))
    queries = [
        Query(id="q1", text="сверхпроводимость купратов", expect="in-domain"),
        Query(id="q2", text="vehicle routing", expect="in-domain"),
    ]
    run = run_queries(backend, queries, k=2)
    assert run.variant == "e5-base"
    assert run.ranked_ids("q1")[0] == "A2"
    assert run.top_score("q1") is not None

    path = save_run(run, tmp_path / "runs")
    assert load_run(path).ranked_ids("q1") == run.ranked_ids("q1")

    pool = build_pool([run], depth=2)
    assert len(pool) == 4
    assert pool == sorted(pool)  # sorted by (query, author) — the judge stays blind to the model


def test_load_profiles_applies_cleaning_only_to_the_indexed_text(tmp_path: Path) -> None:
    path = tmp_path / "profiles.jsonl"
    profile = {
        "id": "A1",
        "name": "A. Author",
        "institution": "МФТИ",
        "h_index": 5,
        "topics": ["Particle physics"],
        "profile_text": "A. Author — МФТИ.\n«T» (2020). Sample of $\\ensuremath{\\psi}$ events.",
        "works": [],
    }
    path.write_text(json.dumps(profile, ensure_ascii=False) + "\n", encoding="utf-8")
    raw = load_profiles(path, clean=False)[0]
    cleaned = load_profiles(path, clean=True)[0]
    assert "\\ensuremath" in raw.indexed_text
    assert "\\ensuremath" not in cleaned.indexed_text
    assert cleaned.profile_text == raw.profile_text  # the export itself is never rewritten


def test_missing_profiles_file_points_at_the_etl(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="sfr-etl"):
        load_profiles(tmp_path / "nope.jsonl")


def test_empty_profiles_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "profiles.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_profiles(path)


def test_numpy_scan_matches_faiss_exactly(
    tmp_path: Path, profiles: list[ProfileRecord], fake_embedder: type
) -> None:
    """The search path is NumPy, the artefact is FAISS — they must not diverge.

    (This test never loads torch, so FAISS is safe to call here; see runtime.py.)
    """
    import numpy as np

    from sfr_match.index import load_faiss_vectors, load_vectors
    from sfr_match.runtime import import_faiss, top_k

    spec, out_dir, _, _ = _build(tmp_path, profiles, "e5-base", fake_embedder)
    vectors = load_vectors(out_dir)
    assert np.allclose(vectors, load_faiss_vectors(out_dir))

    query = fake_embedder(spec).encode(["сверхпроводимость купратов"], is_query=True)
    faiss = import_faiss()
    faiss_index = faiss.read_index(str(out_dir / "index.faiss"))
    faiss_scores, faiss_order = faiss_index.search(query, 3)

    order, scores = top_k(vectors, query, 3)
    assert order == [int(i) for i in faiss_order[0]]
    assert np.allclose(scores, faiss_scores[0], atol=1e-6)
