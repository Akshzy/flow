"""Unit tests: configuration loading and validation."""

import pytest

from app.config import ConfigError, Settings, load_settings


def test_settings_defaults(app_settings):
    assert app_settings.environment == "development"
    assert app_settings.log_level == "INFO"
    assert app_settings.log_json is False


def test_settings_parses_database_url(app_settings):
    url = str(app_settings.database_url)
    assert url.startswith("postgresql")
    assert "55433" in url


def test_settings_from_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "ENVIRONMENT=production\n"
        "DATABASE_URL=postgresql+psycopg://user:pw@localhost:5432/floww\n"
        "LOG_LEVEL=DEBUG\n"
        "LOG_JSON=true\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_JSON", raising=False)

    settings = load_settings()
    assert settings.environment == "production"
    assert settings.log_level == "DEBUG"
    assert settings.log_json is True
    assert "5432" in str(settings.database_url)


def test_missing_database_url_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    # The error names the missing field and contains no raw values.
    assert "database_url" in str(excinfo.value)
    assert "postgresql" not in str(excinfo.value)


def test_invalid_environment_fails(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    assert "environment" in str(excinfo.value)


def test_invalid_database_url_fails(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "not-a-valid-url")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    assert "database_url" in str(excinfo.value)


def test_config_error_does_not_expose_secret_values(monkeypatch):
    """An invalid DATABASE_URL containing a password must not leak it."""
    monkeypatch.setenv("DATABASE_URL", "super-secret-password-value")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    assert "super-secret-password-value" not in str(excinfo.value)


def test_settings_direct_validation_error(tmp_path, monkeypatch):
    from pydantic import ValidationError

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError):
        Settings()


def test_create_app_missing_config_fails(tmp_path, monkeypatch):
    from app.main import create_app

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError) as excinfo:
        create_app()
    assert "database_url" in str(excinfo.value)
