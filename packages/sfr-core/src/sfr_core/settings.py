"""Application settings loaded from environment / .env."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """SFR configuration.

    ``OPENALEX_MAILTO`` is mandatory (OpenAlex polite pool): startup fails with a
    clear error when it is missing or obviously invalid.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openalex_mailto: str
    sfr_db_url: str = "sqlite:///data/sfr.db"

    openalex_base_url: str = "https://api.openalex.org"
    openalex_max_rps: float = 10.0

    data_dir: Path = Path("data")
    raw_cache_dir: Path = Path("data/raw")

    # is_supervisor_candidate heuristic thresholds (SPEC §3) — configurable, not code.
    supervisor_min_works: int = 10
    supervisor_min_h_index: int = 5
    supervisor_recent_years: int = 3

    # Works ingest defaults (SPEC §4).
    works_since_years: int = 5
    works_per_author: int = 25

    # profile_text bounds (SPEC §3).
    profile_text_min_chars: int = 300
    profile_text_max_chars: int = 1500

    @field_validator("openalex_mailto")
    @classmethod
    def _mailto_must_look_like_email(cls, value: str) -> str:
        value = value.strip()
        if not value or "@" not in value:
            msg = (
                "OPENALEX_MAILTO is required for the OpenAlex polite pool. "
                "Set it in .env or the environment (see .env.example)."
            )
            raise ValueError(msg)
        return value


def get_settings() -> Settings:
    """Load settings; raises a validation error with a clear message if env is incomplete."""
    return Settings()  # type: ignore[call-arg]  # fields come from the environment
