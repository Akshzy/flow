"""Floww backend application.

Provides the API foundation:

- ``GET /health``  — liveness probe: the process is up. Deliberately does not
  check dependencies, so a database outage does not fail liveness.
- ``GET /ready``   — readiness probe: verifies actual dependency state
  (database connectivity) and reports 503 when the database is unreachable.
- consistent error handling (see ``app.errors``)
- structured logging with secret redaction (see ``app.logging``)
- request ID middleware (see ``app.middleware``)
- authentication + multi-tenancy API (Phase 2, see ``app.routers.auth`` and
  ``app.routers.tenants``)

The app is created through the ``create_app`` factory so configuration is
resolved at startup (not at import time). Run with:

    uvicorn app.main:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.config import Settings, load_settings
from app.db import create_engine, create_session_factory, describe_url, ping
from app.logging import configure_logging, get_request_id
from app.middleware import RequestIdMiddleware
from app.routers import auth as auth_router
from app.routers import connections as connections_router
from app.routers import tenants as tenants_router
from app.webhooks import router as webhook_router

_HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


def _error_payload(
    code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error, "request_id": get_request_id()}


async def _ping_database(engine: Any) -> None:
    await ping(engine)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application.

    Raises ``ConfigError`` (with a clear, secret-free message) when required
    configuration is missing or invalid.
    """
    if settings is None:
        settings = load_settings()

    configure_logging(level=settings.log_level, json_output=settings.log_json)
    logger = structlog.get_logger("app")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "application.startup",
            version=__version__,
            environment=settings.environment,
            database=describe_url(settings.database_url),
        )
        engine = create_engine(settings.database_url)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        try:
            # Verify the database connection at startup. A database outage is
            # reported (and observed in logs) but does not crash startup —
            # the readiness endpoint reflects the actual state.
            await _ping_database(engine)
            logger.info("application.database_connected")
        except Exception as exc:
            logger.warning("application.database_unreachable", error=describe_url(str(exc)))
        try:
            yield
        finally:
            await engine.dispose()
            logger.info("application.shutdown")

    app = FastAPI(
        title="Floww API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )
    app.add_middleware(RequestIdMiddleware)
    # CORS: explicit origins from configuration (no wildcard + credentials).
    # Bearer tokens are used instead of cookies, so CSRF is not applicable.
    allowed_origins = [
        origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    )

    # --- Error handlers -----------------------------------------------------
    from app.errors import AppError  # local import to keep module graph simple

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("api.app_error", code=exc.code, message=exc.message, status=exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_ERROR_CODES.get(exc.status_code, "error")
        logger.warning("api.http_error", code=code, status=exc.status_code, detail=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Whitelist error fields: never include raw input values (which could
        # contain credentials or other sensitive data) in the response.
        details = [
            {"loc": err.get("loc"), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        logger.warning("api.validation_error", count=len(details))
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "validation_error", "Request validation failed.", {"errors": details}
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Full detail (including stack trace) is logged server-side only.
        # The response is generic and never exposes internals or secrets.
        logger.exception("api.unhandled_exception", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=_error_payload("internal_error", "Internal server error."),
        )

    # --- Health / readiness -------------------------------------------------
    @app.get("/health")
    async def health(request: Request) -> dict[str, Any]:
        # Liveness: the process is up. Dependency state is intentionally not
        # checked here (that is the readiness probe's job).
        app_settings: Settings = request.app.state.settings
        return {
            "status": "ok",
            "version": __version__,
            "environment": app_settings.environment,
        }

    app.include_router(auth_router.router)
    app.include_router(tenants_router.router)
    app.include_router(connections_router.router)
    app.include_router(webhook_router.router)

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        engine = getattr(request.app.state, "engine", None)
        if engine is None:
            return JSONResponse(
                status_code=503,
                content=_error_payload(
                    "not_initialized", "Application dependencies are not initialized."
                ),
            )
        try:
            await _ping_database(engine)
        except Exception as exc:
            logger.warning(
                "readiness.database_failed",
                error=describe_url(str(exc)),
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "checks": {"database": "failed"},
                    "error": {
                        "code": "database_unavailable",
                        "message": "Database is not reachable.",
                    },
                    "request_id": get_request_id(),
                },
            )
        app_settings: Settings = request.app.state.settings
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "checks": {"database": "ok"},
                "version": __version__,
                "environment": app_settings.environment,
            },
        )

    return app
