"""Embedding backends. Dense models are loaded lazily — importing this module is cheap."""

from collections.abc import Sequence
from typing import Protocol

import numpy as np

from sfr_match.models import ModelSpec

DEFAULT_BATCH_SIZE = 16


class Embedder(Protocol):
    """Minimal protocol so tests can substitute a deterministic fake."""

    dim: int

    def encode(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray: ...


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalisation — turns inner product into cosine similarity."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized: np.ndarray = (vectors / norms).astype("float32")
    return normalized


class SentenceTransformerEmbedder:
    """sentence-transformers on CPU, with the per-model query/document prefixes."""

    def __init__(self, spec: ModelSpec, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        from sentence_transformers import SentenceTransformer  # slow import, keep it local

        if spec.hf_id is None:
            raise ValueError(f"model {spec.key!r} is not a dense model")
        self.spec = spec
        self.batch_size = batch_size
        self.model = SentenceTransformer(spec.hf_id, device="cpu")
        # sentence-transformers 6 renamed the accessor; keep both working.
        get_dim = getattr(self.model, "get_embedding_dimension", None) or (
            self.model.get_sentence_embedding_dimension
        )
        self.dim = int(get_dim() or 0)

    def encode(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray:
        prepare = self.spec.prepare_query if is_query else self.spec.prepare_document
        prepared = [prepare(text) for text in texts]
        vectors = self.model.encode(
            prepared,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=False,
        )
        return l2_normalize(np.asarray(vectors, dtype="float32"))


def make_embedder(spec: ModelSpec) -> Embedder:
    return SentenceTransformerEmbedder(spec)
