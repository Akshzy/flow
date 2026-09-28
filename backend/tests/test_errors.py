"""API tests: consistent error handling and failure paths."""

from contextlib import asynccontextmanager

import httpx
from pydantic import BaseModel
from structlog.testing import capture_logs


def _settings_with_url(url: str):
    from app.config import Settings

    return Settings(database_url=url, environment="test", log_level="WARNING")


@asynccontextmanager
async def _client_for(application, *, raise_app_exceptions: bool = True):
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application, raise_app_exceptions=raise_app_exceptions)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


class _Body(BaseModel):
    q: int
    password: str


async def test_validation_error_envelope_and_no_secret_leak(app_settings):
    """Invalid request bodies return the error envelope and never leak values."""
    from app.main import create_app

    application = create_app(settings=app_settings)

    @application.post("/_validation")
    async def _validation(body: _Body) -> dict:  # pragma: no cover - test vehicle
        return {}

    async with _client_for(application) as client:
        response = await client.post(
            "/_validation",
            json={"q": "not-an-int", "password": "super-secret-value"},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"]
    assert isinstance(body["error"]["details"]["errors"], list)
    # Raw input values (including the secret) must not appear in the response.
    assert "super-secret-value" not in response.text
    assert "not-an-int" not in response.text
    assert body["request_id"]


async def test_unexpected_error_returns_generic_response(app_settings):
    """Unexpected exceptions return a generic 500 without internal details."""
    from app.main import create_app

    application = create_app(settings=app_settings)

    @application.get("/_boom")
    async def _boom() -> dict:  # pragma: no cover - test vehicle
        raise RuntimeError("boom-with-internal-detail")

    # raise_app_exceptions=False mirrors a real server: the 500 envelope that
    # the server error middleware already sent is returned to the client.
    async with _client_for(application, raise_app_exceptions=False) as client:
        response = await client.get("/_boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "Internal server error."
    # Internal details, exception types and stack traces stay out of the body.
    assert "boom-with-internal-detail" not in response.text
    assert "RuntimeError" not in response.text
    assert "traceback" not in response.text.lower()
    assert body["request_id"]


async def test_unexpected_error_is_logged_server_side(app_settings):
    """The exception is logged (server-side) for observability."""
    from app.main import create_app

    application = create_app(settings=app_settings)

    @application.get("/_boom")
    async def _boom() -> dict:  # pragma: no cover - test vehicle
        raise RuntimeError("boom-with-internal-detail")

    async with _client_for(application, raise_app_exceptions=False) as client:
        with capture_logs() as logs:
            await client.get("/_boom")

    events = [e for e in logs if e.get("event") == "api.unhandled_exception"]
    assert events, "unhandled exception was not logged"
    assert events[0].get("error_type") == "RuntimeError"


async def test_database_failure_returns_503():
    """/ready reports actual state: 503 when the database is unreachable."""
    from app.main import create_app

    application = create_app(
        _settings_with_url("postgresql+psycopg://postgres:postgres@127.0.0.1:1/none")
    )

    async with _client_for(application) as client:
        ready = await client.get("/ready")
        health = await client.get("/health")

    assert ready.status_code == 503
    body = ready.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "failed"
    assert body["error"]["code"] == "database_unavailable"
    assert body["request_id"]
    # Liveness stays healthy; readiness reflects the dependency failure.
    assert health.status_code == 200


async def test_app_error_handler(app_settings):
    """Application errors map to the consistent envelope."""
    from app.errors import NotFoundError
    from app.main import create_app

    application = create_app(settings=app_settings)

    @application.get("/_app-error")
    async def _app_error() -> dict:  # pragma: no cover - test vehicle
        raise NotFoundError("Thing was not found.", details={"thing_id": 7})

    async with _client_for(application) as client:
        response = await client.get("/_app-error")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Thing was not found."
    assert body["error"]["details"] == {"thing_id": 7}
    assert body["request_id"]


async def test_error_response_request_id_matches_header(app_settings):
    from app.main import create_app

    application = create_app(settings=app_settings)

    async with _client_for(application) as client:
        response = await client.get("/nope")

    body = response.json()
    assert body["request_id"] == response.headers["x-request-id"]
