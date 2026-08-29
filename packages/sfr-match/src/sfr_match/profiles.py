"""Loading ``data/exports/profiles.jsonl`` (the SFR-0 hand-off artefact)."""

import json
from dataclasses import dataclass
from pathlib import Path

from sfr_core.schemas import ProfileExport
from sfr_match.cleaning import clean_profile_text

DEFAULT_PROFILES_PATH = Path("data/exports/profiles.jsonl")


@dataclass(frozen=True)
class ProfileRecord:
    """One supervisor profile plus the exact text that was indexed."""

    id: str
    name: str
    institution: str | None
    h_index: int | None
    topics: list[str]
    profile_text: str
    indexed_text: str


def load_profiles(path: Path | None = None, *, clean: bool = False) -> list[ProfileRecord]:
    """Read the export; ``clean=True`` applies the SFR-1 preprocessor at index time.

    The raw JSONL is never rewritten (SPEC_SFR1 §5).
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
            text = clean_profile_text(export.profile_text) if clean else export.profile_text
            records.append(
                ProfileRecord(
                    id=export.id,
                    name=export.name,
                    institution=export.institution,
                    h_index=export.h_index,
                    topics=list(export.topics),
                    profile_text=export.profile_text,
                    indexed_text=text,
                )
            )
    if not records:
        raise ValueError(f"{path} is empty")
    return records
