"""Reconstruct abstract text from OpenAlex ``abstract_inverted_index``."""

from typing import Any


def reconstruct_abstract(inverted_index: dict[str, Any] | None) -> str | None:
    """Rebuild the abstract: place each word at its positions, join with spaces.

    Tolerates broken input (non-list positions, non-int entries, negative indices);
    returns None when nothing meaningful can be reconstructed.
    """
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, indices in inverted_index.items():
        if not isinstance(indices, list):
            continue
        for index in indices:
            if isinstance(index, int) and not isinstance(index, bool) and index >= 0:
                positions.append((index, word))
    if not positions:
        return None
    positions.sort()
    text = " ".join(word for _, word in positions).strip()
    return text or None
