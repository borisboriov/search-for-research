"""FAISS/torch coexistence guard.

``faiss-cpu`` and ``torch`` each ship their own copy of libomp. On macOS the second
one to initialise aborts the process (``OMP: Error #15``) as soon as FAISS enters a
parallel region — i.e. on ``IndexFlatIP.search``. Import order does not help, and
neither does ``omp_set_num_threads(1)``; the only documented switch,
``KMP_DUPLICATE_LIB_OK=TRUE``, is described upstream as possibly producing silently
incorrect results — unacceptable for an experiment whose whole output is numbers.

So the split is: FAISS **writes** the index (the artefact SFR-2 will serve from),
and the query-time top-k is an exact NumPy inner-product scan over the same vectors
(261 profiles — exact, sub-millisecond, and equal to FAISS by construction; the
equality is asserted in the tests). Nothing on the search path imports FAISS.

Writing is still safe in a process that also holds torch, as long as torch was
imported first — ``build_index`` guarantees that by creating the embedder before
importing FAISS.
"""

from types import ModuleType

import numpy as np


def import_faiss() -> ModuleType:
    """Import FAISS. Only for building/reading index files, never for searching."""
    import faiss

    return faiss


def top_k(matrix: np.ndarray, query: np.ndarray, k: int) -> tuple[list[int], list[float]]:
    """Exact top-k by inner product (== cosine, the vectors are L2-normalised)."""
    scores = matrix @ query.reshape(-1)
    k = min(k, scores.shape[0])
    # argpartition for the cut, then sort just the k survivors — stable on ties by index.
    candidates = np.argpartition(-scores, k - 1)[:k] if k < scores.shape[0] else np.arange(k)
    ordered = candidates[np.argsort(-scores[candidates], kind="stable")]
    return [int(i) for i in ordered], [float(scores[i]) for i in ordered]
