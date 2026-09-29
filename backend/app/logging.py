"""Structured logging built on structlog.

- JSON output in production-like environments, human-readable console output
  in development.
- Every log record is passed through a redaction processor that removes
  sensitive values (passwords, tokens, API keys, authorization headers,
  private keys, database credentials) before rendering.
- Request IDs are bound to the logging context per request (see
  ``app.middleware``) so records can be correlated and included in error
  responses.
"""

import logging
from typing import Any

import structlog

REDACTED = "[REDACTED]"

# Substring markers (case-insensitive, matched against key names). A key whose
# normalized name contains any of these is redacted. Chosen to avoid common
# false positives such as "author" (only "authorization" matches).
_SENSITIVE_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
    "cookie",
    "database_url",
    "dsn",
)


def _normalized(key: Any) -> str:
    return str(key).lower().replace("-", "_")


def _is_sensitive_key(key: Any) -> bool:
    normalized = _normalized(key)
    return any(marker in normalized for marker in _SENSITIVE_MARKERS)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: REDACTED if _is_sensitive_key(k) else _redact_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


def redact_sensitive(
    logger: Any, method_name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Structlog processor: redact sensitive values from the event dict."""
    return {
        key: REDACTED if _is_sensitive_key(key) else _redact_value(value)
        for key, value in event_dict.items()
    }


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure structlog for the application.

    ``json_output=True`` renders each record as a single JSON line (used in
    production/test); otherwise a human-readable console renderer is used
    (development).
    """
    numeric_level = logging.getLevelNamesMapping().get(level.upper())
    if numeric_level is None:
        raise ValueError(f"Invalid LOG_LEVEL: {level!r}")

    renderer: structlog.types.Processor
    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        # No file argument: PrintLoggerFactory() resolves sys.stdout at logger
        # creation time (per call, since cache_logger_on_first_use=False), so
        # the stream is never a stale reference — binding sys.stdout here
        # would capture the object at configure time, which breaks (I/O on a
        # closed stream) after stdout capture is restored (e.g. pytest).
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_request_id() -> str | None:
    """Return the request ID bound to the current context, if any."""
    return structlog.contextvars.get_contextvars().get("request_id")
