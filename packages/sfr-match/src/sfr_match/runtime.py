"""Which library actually answers a query: FAISS where it is safe, NumPy where it is not.

``faiss-cpu`` and ``torch`` each ship their own copy of libomp. On macOS the second
one to initialise aborts the process (``OMP: Error #15``) as soon as FAISS enters a
parallel region — i.e. on ``IndexFlatIP.search``. Import order does not help, and
neither does ``omp_set_num_threads(1)``; the only documented switch,
``KMP_DUPLICATE_LIB_OK=TRUE``, is described upstream as possibly producing silently
incorrect results — unacceptable for an experiment whose whole output is numbers.

On Linux (the container, CI, the future VPS) there is no such conflict, so SFR-2 puts
FAISS back on the search path and picks the searcher by platform:

* Linux → ``FaissSearcher`` (``IndexFlatIP.search``);
* macOS → ``NumpySearcher``, an exact inner-product scan over the same vectors;
* ``SFR_SEARCH_BACKEND=faiss|numpy`` forces either one (used by the tests).

Both are exact — a flat index does no approximation — so the two paths return the
same ranking; the equality is asserted in the tests rather than assumed.

Writing the index is safe in either process, as long as torch was imported first —
``build_index`` guarantees that by creating the embedder before importing FAISS.
"""

import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Protocol

import numpy as np

SEARCH_BACKEND_ENV = "SFR_SEARCH_BACKEND"
BACKENDS = ("auto", "faiss", "numpy")


def import_faiss() -> ModuleType:
    import faiss

    return faiss


def select_search_backend(platform: str | None = None, env: dict[str, str] | None = None) -> str:
    """``faiss`` everywhere except macOS; an env override wins over the platform."""
    environ = os.environ if env is None else env
    choice = environ.get(SEARCH_BACKEND_ENV, "auto").strip().lower() or "auto"
    if choice not in BACKENDS:
        raise ValueError(f"{SEARCH_BACKEND_ENV}={choice!r}; expected one of {', '.join(BACKENDS)}")
    if choice != "auto":
        return choice
    return "numpy" if (platform or sys.platform) == "darwin" else "faiss"


def top_k(matrix: np.ndarray, query: np.ndarray, k: int) -> tuple[list[int], list[float]]:
    """Exact top-k by inner product (== cosine, the vectors are L2-normalised)."""
    scores = matrix @ query.reshape(-1)
    k = min(k, scores.shape[0])
    # argpartition for the cut, then sort just the k survivors — stable on ties by index.
    candidates = np.argpartition(-scores, k - 1)[:k] if k < scores.shape[0] else np.arange(k)
    ordered = candidates[np.argsort(-scores[candidates], kind="stable")]
    return [int(i) for i in ordered], [float(scores[i]) for i in ordered]


class Searcher(Protocol):
    name: str

    def top_k(self, query: np.ndarray, k: int) -> tuple[list[int], list[float]]: ...


class NumpySearcher:
    """Exact inner-product scan. No FAISS import — safe next to torch on macOS."""

    name = "numpy"

    def __init__(self, vectors: np.ndarray) -> None:
        self.vectors = vectors

    def top_k(self, query: np.ndarray, k: int) -> tuple[list[int], list[float]]:
        return top_k(self.vectors, query, k)


class FaissSearcher:
    """``IndexFlatIP.search`` over the index file written at build time."""

    name = "faiss"

    def __init__(self, index_file: Path) -> None:
        faiss = import_faiss()
        self.index = faiss.read_index(str(index_file))

    def top_k(self, query: np.ndarray, k: int) -> tuple[list[int], list[float]]:
        k = min(k, int(self.index.ntotal))
        scores, order = self.index.search(np.ascontiguousarray(query.reshape(1, -1)), k)
        return [int(i) for i in order[0]], [float(s) for s in scores[0]]


def make_searcher(index_file: Path, vectors: np.ndarray) -> Searcher:
    """Pick the searcher for this platform; fall back to NumPy if the FAISS file is absent."""
    if select_search_backend() == "faiss" and index_file.exists():
        return FaissSearcher(index_file)
    return NumpySearcher(vectors)
