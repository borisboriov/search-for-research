"""Shared fixtures: a deterministic fake embedder so unit tests never load a real model."""

from collections.abc import Sequence
from zlib import crc32

import numpy as np
import pytest

from sfr_match.embedders import l2_normalize
from sfr_match.models import ModelSpec
from sfr_match.profiles import ProfileRecord

DIM = 64


class FakeEmbedder:
    """Hashes text into a fixed-size bag-of-words vector: deterministic, fast, no downloads.

    ``crc32`` rather than ``hash`` — the built-in is salted per process, which would
    make rankings differ between runs.

    Implements the ``Embedder`` protocol, and records what it was asked to encode
    so tests can assert on the per-model prefixes.
    """

    def __init__(self, spec: ModelSpec, dim: int = DIM) -> None:
        self.spec = spec
        self.dim = dim
        self.seen: list[tuple[str, bool]] = []

    def encode(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray:
        prepare = self.spec.prepare_query if is_query else self.spec.prepare_document
        vectors = np.zeros((len(texts), self.dim), dtype="float32")
        for row, text in enumerate(texts):
            prepared = prepare(text)
            self.seen.append((prepared, is_query))
            for token in prepared.lower().split():
                vectors[row, crc32(token.encode()) % self.dim] += 1.0
        return l2_normalize(vectors)


@pytest.fixture
def fake_embedder() -> type[FakeEmbedder]:
    """The fake embedder class itself — tests instantiate it per model spec."""
    return FakeEmbedder


@pytest.fixture
def profiles() -> list[ProfileRecord]:
    def record(author_id: str, name: str, text: str) -> ProfileRecord:
        return ProfileRecord(
            id=author_id,
            name=name,
            institution="МФТИ",
            h_index=10,
            topics=["Topic"],
            profile_text=text,
            indexed_text=text,
        )

    return [
        record("A1", "Первый", "нейросети обработка текстов депрессия соцсети"),
        record("A2", "Второй", "сверхпроводимость купратов и магнетизм"),
        record("A3", "Третий", "vehicle routing optimization logistics algorithms"),
    ]
