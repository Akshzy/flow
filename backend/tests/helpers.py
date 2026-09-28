"""Shared test helpers for Phase 2 (authentication + multi-tenancy)."""

import uuid

import httpx

PASSWORD = "correct-horse-battery-42"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


async def register_and_login(
    client: httpx.AsyncClient,
    email: str | None = None,
    password: str = PASSWORD,
) -> tuple[str, dict]:
    """Register a user and log in; returns (token, user dict)."""
    email = email or unique_email()
    response = await client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    user = response.json()

    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"], user


async def create_tenant(client: httpx.AsyncClient, token: str, name: str) -> dict:
    """Create a tenant as the token's user; returns the tenant dict."""
    response = await client.post("/tenants", json={"name": name}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()
