"""Fixtures for the API tests: a fake backend, so no model and no index are loaded."""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

from sfr_match.index import IndexMeta
from sfr_match.search import Hit

DOCS: list[dict[str, object]] = [
    {
        "id": "A1",
        "name": "Л. В. Инжечик",
        "institution": "МФТИ",
        "h_index": 31,
        "works_count": 412,
        "topics": ["Neutrino Physics", "Dark Matter"],
        "profile_text": "Л. В. Инжечик — МФТИ. GERDA, 0νββ в Ge-76.",
        "display_text": "Л. В. Инжечик — МФТИ. GERDA, 0νββ в Ge-76.",
        "indexed_text": "нейтрино безнейтринный двойной бета распад германий",
    },
    {
        "id": "A2",
        "name": "Anton Agafonov",
        "institution": "МГУ",
        "h_index": 12,
        "works_count": 90,
        "topics": ["Transportation Planning and Optimization"],
        "profile_text": "Anton Agafonov — МГУ. Маршрутизация и транспортные сети.",
        "display_text": "Anton Agafonov — МГУ. Маршрутизация и транспортные сети.",
        "indexed_text": "оптимизация маршрутов логистика транспортные сети",
    },
    {
        "id": "A3",
        "name": "V. A. Knyaz",
        "institution": "МФТИ",
        "h_index": 18,
        "works_count": 256,
        "topics": ["Dental Radiography and Imaging"],
        "profile_text": "V. A. Knyaz — МФТИ. ThermalGAN, pix2pix, медицинские изображения.",
        "display_text": "V. A. Knyaz — МФТИ. ThermalGAN, pix2pix, медицинские изображения.",
        "indexed_text": "нейросети медицинские изображения сегментация",
    },
]


def make_meta(n_profiles: int = 3) -> IndexMeta:
    return IndexMeta(
        model_key="frida",
        hf_id="ai-forever/FRIDA",
        kind="dense",
        clean=True,
        n_profiles=n_profiles,
        dim=1536,
        build_seconds=453.9,
        query_prefix="search_query: ",
        document_prefix="search_document: ",
        compose="full",
        built_at="2026-08-29T18:00:00+00:00",
        corpus_sha="0123456789abcdef",
    )


class FakeBackend:
    """Ranks by word overlap and hands out descending scores from ``top_score``.

    Implements the ``sfr_match.search.Backend`` protocol — that is the whole point:
    the API must not care whether FRIDA or a fake is behind it.
    """

    def __init__(self, top_score: float = 0.5, docs: list[dict[str, object]] | None = None) -> None:
        self.docs = DOCS if docs is None else docs
        self.meta = make_meta(len(self.docs))
        self.top_score = top_score
        self.warmups = 0
        self.queries: list[str] = []

    def warmup(self) -> None:
        self.warmups += 1

    def search(self, query: str, k: int = 10) -> list[Hit]:
        self.queries.append(query)
        tokens = set(query.lower().split())
        ranked = sorted(
            self.docs,
            key=lambda doc: -len(tokens & set(str(doc["indexed_text"]).lower().split())),
        )
        return [
            Hit(
                rank=rank,
                author_id=str(doc["id"]),
                name=str(doc["name"]),
                score=round(self.top_score - 0.01 * (rank - 1), 4),
                topics=list(doc["topics"]),  # type: ignore[arg-type]
                profile_text=str(doc["display_text"]),
                institution=str(doc["institution"]),
                h_index=int(doc["h_index"]),  # type: ignore[call-overload]
                works_count=int(doc["works_count"]),  # type: ignore[call-overload]
            )
            for rank, doc in enumerate(ranked[:k], start=1)
        ]


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


def write_index(directory: Path, docs: list[dict[str, object]] | None = None) -> Path:
    """A real index directory on disk, without embedding anything."""
    docs = DOCS if docs is None else docs
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "docs.json").write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    meta = make_meta(len(docs))
    (directory / "meta.json").write_text(
        json.dumps(asdict(meta), ensure_ascii=False), encoding="utf-8"
    )
    np.save(directory / "vectors.npy", np.eye(len(docs), 8, dtype="float32"))
    return directory
