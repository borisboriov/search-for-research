"""Pinned native verifier and repository resources, independent of Pi configuration."""

from pathlib import Path


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "uv.lock").is_file() and (parent / "enrichment/pyproject.toml").is_file():
            return parent
    raise ValueError("Run enrichment from its versioned SFR repository checkout")


RUBRIC = repository_root() / "enrichment/configs/verifier-v3.md"
HIGH_CONFIGS = {"native_verifier": {"provider": "openai", "model": "gpt-6.1-sol", "effort": "high"}}
