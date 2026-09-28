"""API tests: health and readiness endpoints (against the real app + database)."""

import httpx
import pytest


async def test_health_returns_ok(client: httpx.AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["environment"] in ("development", "test", "production")


async def test_health_has_request_id_header(client: httpx.AsyncClient):
    response = await client.get("/health")
    request_id = response.headers.get("x-request-id")
    assert request_id
    assert len(request_id) == 32  # uuid4().hex


async def test_request_ids_are_unique_per_request(client: httpx.AsyncClient):
    first = (await client.get("/health")).headers["x-request-id"]
    second = (await client.get("/health")).headers["x-request-id"]
    assert first != second


async def test_ready_returns_ok_when_database_up(client: httpx.AsyncClient):
    response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


async def test_health_is_independent_of_database():
    """Liveness must not fail when the database is unreachable."""
    import httpx as _httpx

    from app.main import create_app

    application = create_app(
        _settings_with_url("postgresql+psycopg://postgres:postgres@127.0.0.1:1/none")
    )
    async with application.router.lifespan_context(application):
        transport = _httpx.ASGITransport(app=application)
        async with _httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            health = await c.get("/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"

            ready = await c.get("/ready")
            assert ready.status_code == 503


def _settings_with_url(url: str):
    import os

    from app.config import Settings

    return Settings(
        database_url=url,
        environment=os.environ.get("ENVIRONMENT", "test"),
        log_level="WARNING",
    )


@pytest.mark.parametrize(
    "method,path,expected_status",
    [
        ("get", "/nope", 404),
        ("post", "/health", 405),
        ("delete", "/ready", 405),
    ],
)
async def test_unknown_routes_and_methods(
    client: httpx.AsyncClient, method: str, path: str, expected_status: int
):
    response = await getattr(client, method)(path)
    assert response.status_code == expected_status
    body = response.json()
    assert "error" in body
    assert body["error"]["code"]
    assert body["error"]["message"]
