"""Unit tests for settings that must work without external services."""

from app.core.config import Settings


def test_settings_do_not_require_external_credentials() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.database_url is None
    assert settings.llm_api_key is None
