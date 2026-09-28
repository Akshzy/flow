"""Application configuration.

Configuration is loaded from environment variables (optionally from a local
``.env`` file next to the backend package). Required values fail clearly and
early. No production secrets may ever be committed to the repository; use
``.env.example`` as a template for required variables.
"""

from typing import Literal

from pydantic import PostgresDsn, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid.

    The message is safe to display: it contains field names only, never
    raw input values (which could contain credentials).
    """


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = "development"
    database_url: PostgresDsn
    log_level: str = "INFO"
    log_json: bool = False
    session_ttl_hours: int = 168  # auth session lifetime (default: 7 days)
    cors_origins: str = "http://localhost:3000"  # comma-separated allowed origins


def _validation_field_names(exc: ValidationError) -> str:
    """Extract field names from a validation error, without input values."""
    names: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        names.append(loc or "<unknown>")
    return ", ".join(sorted(set(names)))


def load_settings() -> Settings:
    """Load settings from the environment, raising a clear error on failure.

    The raised ``ConfigError`` deliberately contains field names only —
    never raw values, which could contain credentials.
    """
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigError(
            f"Missing or invalid configuration: {_validation_field_names(exc)}"
        ) from None
