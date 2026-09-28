"""Consistent API error types.

All API errors are returned as a single JSON envelope:

    {"error": {"code": "...", "message": "...", "details": {...}?},
     "request_id": "..."}

Handlers are registered in ``app.main``. Unexpected exceptions are logged
server-side (including stack traces) and returned as a generic ``internal_error``
response that never exposes internal details or secrets.
"""

from typing import Any

import structlog


class AppError(Exception):
    """Base class for application errors that map to an API error response."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"

    def __init__(self, message: str = "Database is not reachable.") -> None:
        super().__init__(message)


def get_logger(name: str | None = None) -> structlog.types.FilteringBoundLogger:
    """Return a structlog logger (convenience wrapper)."""
    return structlog.get_logger(name)
