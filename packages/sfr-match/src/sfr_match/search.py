"""Search backends over a built index: dense (FAISS) and BM25."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from sfr_match.embedders import Embedder, make_embedder
from sfr_match.index import IndexMeta, load_docs, load_meta, load_vectors
from sfr_match.lexical import build_bm25, tokenize
from sfr_match.models import ModelSpec, resolve_model
from sfr_match.runtime import top_k


@dataclass(frozen=True)
class Hit:
    rank: int
    author_id: str
    name: str
    score: float
    topics: list[str]
    profile_text: str


class Backend(Protocol):
    meta: IndexMeta

    def search(self, query: str, k: int = 10) -> list[Hit]: ...

    def warmup(self) -> None:
        """Load whatever is lazy, so it is not charged to the first query's latency."""


def _hits(docs: list[dict[str, Any]], order: list[int], scores: list[float]) -> list[Hit]:
    return [
        Hit(
            rank=rank,
            author_id=str(docs[i]["id"]),
            name=str(docs[i]["name"]),
            score=float(score),
            topics=list(docs[i].get("topics") or []),
            profile_text=str(docs[i]["profile_text"]),
        )
        for rank, (i, score) in enumerate(zip(order, scores, strict=True), start=1)
    ]


class DenseBackend:
    """Inner product over L2-normalised vectors == cosine similarity.

    The index file is written by FAISS; the query-time scan is NumPy (see runtime.py).
    """

    def __init__(self, index_dir: Path, spec: ModelSpec, embedder: Embedder | None = None) -> None:
        self.meta = load_meta(index_dir)
        self.spec = spec
        self.docs: list[dict[str, Any]] = load_docs(index_dir)
        self.vectors = load_vectors(index_dir)
        self._embedder = embedder

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = make_embedder(self.spec)
        return self._embedder

    def warmup(self) -> None:
        self.embedder.encode(["разогрев"], is_query=True)

    def search(self, query: str, k: int = 10) -> list[Hit]:
        vector = self.embedder.encode([query], is_query=True)
        order, scores = top_k(self.vectors, vector, min(k, len(self.docs)))
        return _hits(self.docs, order, scores)


class Bm25Backend:
    """rank-bm25 over the same indexed texts."""

    def __init__(self, index_dir: Path, spec: ModelSpec) -> None:
        self.meta = load_meta(index_dir)
        self.spec = spec
        self.docs: list[dict[str, Any]] = load_docs(index_dir)
        self.bm25 = build_bm25([str(doc["indexed_text"]) for doc in self.docs])

    def warmup(self) -> None:
        """Nothing lazy: the BM25 corpus is built in __init__."""

    def search(self, query: str, k: int = 10) -> list[Hit]:
        scores = np.asarray(self.bm25.get_scores(tokenize(query)))  # type: ignore[attr-defined]
        k = min(k, len(self.docs))
        order = list(np.argsort(-scores)[:k])
        return _hits(self.docs, [int(i) for i in order], [float(scores[i]) for i in order])


def load_backend(index_dir: Path, model: str, embedder: Embedder | None = None) -> Backend:
    spec = resolve_model(model)
    if spec.kind == "bm25":
        return Bm25Backend(index_dir, spec)
    return DenseBackend(index_dir, spec, embedder)
