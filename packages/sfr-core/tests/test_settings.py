import pytest
from pydantic import ValidationError

from sfr_core.settings import Settings


def make_settings(**overrides: object) -> Settings:
    kwargs: dict[str, object] = {"openalex_mailto": "test@example.com"}
    kwargs.update(overrides)
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_mailto_required() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_mailto_must_contain_at() -> None:
    with pytest.raises(ValidationError, match="OPENALEX_MAILTO"):
        make_settings(openalex_mailto="not-an-email")


def test_mailto_blank_rejected() -> None:
    with pytest.raises(ValidationError, match="OPENALEX_MAILTO"):
        make_settings(openalex_mailto="   ")


def test_defaults() -> None:
    settings = make_settings()
    assert settings.sfr_db_url == "sqlite:///data/sfr.db"
    assert settings.supervisor_min_works == 10
    assert settings.supervisor_min_h_index == 5
    assert settings.supervisor_recent_years == 3
    assert settings.openalex_max_rps == 10.0


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENALEX_MAILTO", "env@example.com")
    monkeypatch.setenv("SUPERVISOR_MIN_WORKS", "42")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.openalex_mailto == "env@example.com"
    assert settings.supervisor_min_works == 42
