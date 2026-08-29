"""Loading ``data/exports/profiles.jsonl`` (the SFR-0 hand-off artefact)."""

import json
from dataclasses import dataclass
from pathlib import Path

from sfr_core.schemas import ProfileExport
from sfr_match.cleaning import clean_profile_text
from sfr_match.composition import Composition, compose_indexed_text

DEFAULT_PROFILES_PATH = Path("data/exports/profiles.jsonl")


@dataclass(frozen=True)
class ProfileRecord:
    """One supervisor profile: the card fields, the card text and the indexed text."""

    id: str
    name: str
    institution: str | None
    h_index: int | None
    topics: list[str]
    profile_text: str  # exactly as exported by SFR-0
    indexed_text: str  # what the embedder sees (composition + optional cleaning)
    display_text: str = ""  # what a user sees on the card — always cleaned, never composed
    works_count: int | None = None


def load_profiles(
    path: Path | None = None,
    *,
    clean: bool = False,
    compose: Composition = "full",
) -> list[ProfileRecord]:
    """Read the export; build the indexed text (SPEC_SFR2 §5) and the card text.

    ``compose`` picks what goes into the index, ``clean=True`` then applies the
    SFR-1 preprocessor to it. The raw JSONL is never rewritten (SPEC_SFR1 §5).
    """
    path = path or DEFAULT_PROFILES_PATH
    if not path.exists():
        msg = (
            f"{path} not found — rebuild it with the sfr-etl commands from README "
            "(the data/raw cache makes this almost network-free)"
        )
        raise FileNotFoundError(msg)
    records: list[ProfileRecord] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                export = ProfileExport.model_validate(json.loads(line))
            except Exception as exc:
                raise ValueError(f"{path}:{lineno}: {exc}") from exc
            text = compose_indexed_text(export, compose)
            records.append(
                ProfileRecord(
                    id=export.id,
                    name=export.name,
                    institution=export.institution,
                    h_index=export.h_index,
                    topics=list(export.topics),
                    profile_text=export.profile_text,
                    indexed_text=clean_profile_text(text) if clean else text,
                    display_text=clean_profile_text(export.profile_text),
                    works_count=export.works_count,
                )
            )
    if not records:
        raise ValueError(f"{path} is empty")
    return records
