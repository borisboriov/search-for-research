"""Model registry: the variants compared in SFR-1 (SPEC_SFR1 §3).

Per-model preprocessing lives here, not at the call site: E5 and FRIDA are
asymmetric models and lose a large part of their quality without their prefixes.
"""

from dataclasses import dataclass
from typing import Literal

ModelKind = Literal["dense", "bm25"]


@dataclass(frozen=True)
class ModelSpec:
    key: str
    hf_id: str | None
    kind: ModelKind = "dense"
    query_prefix: str = ""
    document_prefix: str = ""
    params_m: float | None = None  # millions of parameters, for the report table
    note: str = ""

    def prepare_query(self, text: str) -> str:
        return self.query_prefix + text

    def prepare_document(self, text: str) -> str:
        return self.document_prefix + text

    def slug(self, *, clean: bool) -> str:
        return f"{self.key}_clean" if clean else self.key


REGISTRY: dict[str, ModelSpec] = {
    spec.key: spec
    for spec in (
        ModelSpec(
            key="e5-base",
            hf_id="intfloat/multilingual-e5-base",
            query_prefix="query: ",
            document_prefix="passage: ",
            params_m=278.0,
            note="основной кандидат, мультиязычный, асимметричные префиксы",
        ),
        ModelSpec(
            key="mpnet",
            hf_id="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            params_m=278.0,
            note="классический мультиязычный бейзлайн, симметричный",
        ),
        ModelSpec(
            key="frida",
            hf_id="ai-forever/FRIDA",
            query_prefix="search_query: ",
            document_prefix="search_document: ",
            params_m=823.0,
            note="русско-специализированная (топ ruMTEB retrieval < 1.5B)",
        ),
        ModelSpec(
            key="minilm",
            hf_id="sentence-transformers/all-MiniLM-L6-v2",
            params_m=22.7,
            note="англоязычная модель из раннего паспорта проекта — мерим просадку на ru",
        ),
        ModelSpec(
            key="bm25",
            hf_id=None,
            kind="bm25",
            note="лексический бейзлайн (rank-bm25), задел под гибрид",
        ),
    )
}

DEFAULT_MODELS = ["e5-base", "mpnet", "frida", "minilm", "bm25"]


def resolve_model(name: str) -> ModelSpec:
    """Look a model up by short key or by full HuggingFace id."""
    if name in REGISTRY:
        return REGISTRY[name]
    for spec in REGISTRY.values():
        if spec.hf_id == name:
            return spec
    known = ", ".join(REGISTRY)
    raise KeyError(f"unknown model {name!r}; known keys: {known}")
