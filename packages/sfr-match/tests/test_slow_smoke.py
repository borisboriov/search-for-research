"""End-to-end smoke test with a real (small) model. Excluded from CI — see Makefile."""

from pathlib import Path

import pytest

from sfr_match.index import build_index, index_path
from sfr_match.models import resolve_model
from sfr_match.profiles import ProfileRecord
from sfr_match.search import DenseBackend

pytestmark = pytest.mark.slow


def test_real_minilm_index_and_search(tmp_path: Path) -> None:
    spec = resolve_model("minilm")
    profiles = [
        ProfileRecord(
            id=author_id,
            name=author_id,
            institution="МФТИ",
            h_index=1,
            topics=[],
            profile_text=text,
            indexed_text=text,
        )
        for author_id, text in [
            ("A1", "Neural networks for natural language processing and text classification"),
            ("A2", "Superconductivity in cuprates and magnetic properties of thin films"),
        ]
    ]
    out_dir = index_path(spec, clean=False, root=tmp_path)
    meta = build_index(profiles, spec, clean=False, out_dir=out_dir)
    assert meta.dim == 384

    hits = DenseBackend(out_dir, spec).search("deep learning for text", k=2)
    assert hits[0].author_id == "A1"
    assert hits[0].score > hits[1].score
