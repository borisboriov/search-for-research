"""Index building and loading: FAISS ``IndexFlatIP`` over normalised vectors, or BM25.

261 profiles — a flat index is exact and instant; nothing more clever is warranted.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from sfr_match.composition import Composition
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
    # Added in SFR-2; the defaults keep SFR-1 index directories loadable.
    compose: str = "full"
    built_at: str = ""
    corpus_sha: str = ""
    # SFR-5: пороги уверенности, откалиброванные для этого индекса
    # (`sfr-match stamp-thresholds`). Пишутся после сборки — калибровать их
    # можно только по прогонам, — и служат сверкой: settings API и индекс
    # не должны разъехаться незаметно. Источник истины для рантайма — settings.
    thresholds: dict[str, float] | None = None
    # #16: дата данных каталога — самая свежая `updated_date` записи OpenAlex
    # среди авторов каталога (`scripts/stamp_data_date.py`, шаг `make
    # index-sfr5c`). Не `built_at`: индекс пересобирают и без доливки данных,
    # а посетитель читает плашку «обновлено» как «когда обновились данные о
    # человеке». Пусто — индекс без штампа, фронт тогда показывает `built_at`.
    data_updated_at: str = ""

    @property
    def slug(self) -> str:
        base = f"{self.model_key}_clean" if self.clean else self.model_key
        return base if self.compose == "full" else f"{base}__{self.compose}"

    @property
    def version(self) -> str:
        """Identity of the served index — API and index must not drift apart unnoticed."""
        return f"{self.slug}-{self.n_profiles}p-{self.corpus_sha[:8] or 'unknown'}"


def corpus_sha(profiles: list[ProfileRecord]) -> str:
    """Fingerprint of what was indexed: ids and the exact embedded texts."""
    digest = hashlib.sha256()
    for profile in profiles:
        digest.update(profile.id.encode())
        digest.update(b"\x00")
        digest.update(profile.indexed_text.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def index_path(
    spec: ModelSpec,
    *,
    clean: bool,
    compose: Composition = "full",
    root: Path = DEFAULT_INDEX_ROOT,
) -> Path:
    return root / spec.slug(clean=clean, compose=compose)


def _write_docs(out_dir: Path, profiles: list[ProfileRecord]) -> None:
    payload = [
        {
            "id": profile.id,
            "name": profile.name,
            "institution": profile.institution,
            "h_index": profile.h_index,
            "works_count": profile.works_count,
            "topics": profile.topics,
            "profile_text": profile.profile_text,
            "display_text": profile.display_text or profile.profile_text,
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
    compose: Composition = "full",
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
        compose=compose,
        built_at=datetime.now(UTC).isoformat(timespec="seconds"),
        corpus_sha=corpus_sha(profiles),
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


def stamp_data_updated_at(index_dir: Path, value: str) -> IndexMeta:
    """Дописать дату данных каталога в meta.json уже собранного индекса (#16)."""
    meta = load_meta(index_dir)
    meta.data_updated_at = value
    (index_dir / META_FILE).write_text(
        json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def stamp_thresholds(index_dir: Path, thresholds: dict[str, float]) -> IndexMeta:
    """Дописать откалиброванные пороги в meta.json уже собранного индекса."""
    meta = load_meta(index_dir)
    meta.thresholds = dict(thresholds)
    (index_dir / META_FILE).write_text(
        json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


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


def resolve_index_dir(
    model: str,
    *,
    clean: bool,
    compose: Composition = "full",
    root: Path = DEFAULT_INDEX_ROOT,
) -> Path:
    return index_path(resolve_model(model), clean=clean, compose=compose, root=root)


def profile_fingerprints(index_root: Path) -> dict[str, str]:
    """Отпечатки профилей индекса (#123): id → `profile_fingerprint(profile_text)`.

    ``index_root`` — корень (`data/indexes_sfr5c`) или сам каталог индекса.
    """
    from sfr_match.evalset import profile_fingerprint

    candidates = [index_root, *sorted(p for p in index_root.iterdir() if p.is_dir())]
    docs_dir = next(d for d in candidates if (d / "docs.json").exists())
    return {
        str(doc["id"]): profile_fingerprint(str(doc["profile_text"])) for doc in load_docs(docs_dir)
    }
