"""BM25 lexical baseline (SPEC_SFR1 §3.5): lowercase + punctuation stripping, no lemmatisation."""

import re
from collections.abc import Sequence

_TOKEN = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
MIN_TOKEN_LEN = 2


def tokenize(text: str) -> list[str]:
    """Lowercase, drop punctuation, keep tokens of length >= 2."""
    return [token for token in _TOKEN.findall(text.lower()) if len(token) >= MIN_TOKEN_LEN]


def build_bm25(documents: Sequence[str]) -> object:
    from rank_bm25 import BM25Okapi

    return BM25Okapi([tokenize(document) for document in documents])
