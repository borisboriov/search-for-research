"""Index building and loading: FAISS ``IndexFlatIP`` over normalised vectors, or BM25.

261 profiles — a flat index is exact and instant; nothing more clever is warranted.
"""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from sfr_match.embedders import Embedder, make_embedder
from sfr_match.models import ModelSpec, resolve_model
from sfr_match.profiles import ProfileRecord
from sfr_match.runtime import import_faiss

DEFAULT_INDEX_ROOT = Path("data/indexes")
META_FILE = "meta.json"
DOCS_FILE = "docs.json"
VECTORS_FILE = "index.faiss"
ARRAY_FILE = "vectors.npy"


@dataclass
class IndexMeta:
    model_key: str
    hf_id: str | None
    kind: str
    clean: bool
    n_profiles: int
    dim: int | None
    build_seconds: float
    query_prefix: str = ""
    document_prefix: str = ""


def index_path(spec: ModelSpec, *, clean: bool, root: Path = DEFAULT_INDEX_ROOT) -> Path:
    return root / spec.slug(clean=clean)


def _write_docs(out_dir: Path, profiles: list[ProfileRecord]) -> None:
    payload = [
        {
            "id": profile.id,
            "name": profile.name,
            "institution": profile.institution,
            "h_index": profile.h_index,
            "topics": profile.topics,
            "profile_text": profile.profile_text,
            "indexed_text": profile.indexed_text,
        }
        for profile in profiles
    ]
    (out_dir / DOCS_FILE).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def build_index(
    profiles: list[ProfileRecord],
    spec: ModelSpec,
    *,
    clean: bool,
    out_dir: Path,
    embedder: Embedder | None = None,
) -> IndexMeta:
    """Embed (or tokenise) every profile and persist the index next to its metadata."""
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = [profile.indexed_text for profile in profiles]
    started = time.perf_counter()
    dim: int | None = None

    if spec.kind == "dense":
        # The embedder first, FAISS second: torch must initialise libomp before
        # faiss does, or the process aborts on macOS (see runtime.py).
        embedder = embedder or make_embedder(spec)
        vectors = embedder.encode(texts, is_query=False)
        faiss = import_faiss()
        dim = int(vectors.shape[1])
        faiss_index = faiss.IndexFlatIP(dim)
        faiss_index.add(vectors)
        faiss.write_index(faiss_index, str(out_dir / VECTORS_FILE))
        # The same vectors, plain: the search path must not import FAISS (see runtime.py).
        np.save(out_dir / ARRAY_FILE, vectors)
    # BM25 needs no persisted model: the corpus is rebuilt from docs.json on load.

    build_seconds = time.perf_counter() - started
    _write_docs(out_dir, profiles)
    meta = IndexMeta(
        model_key=spec.key,
        hf_id=spec.hf_id,
        kind=spec.kind,
        clean=clean,
        n_profiles=len(profiles),
        dim=dim,
        build_seconds=round(build_seconds, 3),
        query_prefix=spec.query_prefix,
        document_prefix=spec.document_prefix,
    )
    (out_dir / META_FILE).write_text(
        json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def load_meta(index_dir: Path) -> IndexMeta:
    path = index_dir / META_FILE
    if not path.exists():
        raise FileNotFoundError(f"{index_dir} has no index — run `sfr-match index` first")
    return IndexMeta(**json.loads(path.read_text(encoding="utf-8")))


def load_docs(index_dir: Path) -> list[dict[str, object]]:
    return list(json.loads((index_dir / DOCS_FILE).read_text(encoding="utf-8")))


def load_vectors(index_dir: Path) -> np.ndarray:
    """Vectors for search — read from the plain array, not from the FAISS file."""
    vectors: np.ndarray = np.load(index_dir / ARRAY_FILE)
    return vectors


def load_faiss_vectors(index_dir: Path) -> np.ndarray:
    """Vectors as FAISS stored them; used to assert the two files agree."""
    faiss = import_faiss()
    faiss_index = faiss.read_index(str(index_dir / VECTORS_FILE))
    vectors: np.ndarray = faiss_index.reconstruct_n(0, faiss_index.ntotal)
    return vectors


def resolve_index_dir(model: str, *, clean: bool, root: Path = DEFAULT_INDEX_ROOT) -> Path:
    return index_path(resolve_model(model), clean=clean, root=root)
