"""Authentication tests: registration, login, session validation, logout.

All flows run against the real app + PostgreSQL via the test client.
"""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.security import hash_token
from tests.helpers import PASSWORD, auth_headers, register_and_login, unique_email

# --- Registration -----------------------------------------------------------


async def test_register_valid(client: httpx.AsyncClient):
    response = await client.post(
        "/auth/register",
        json={"email": unique_email(), "password": PASSWORD},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"]
    assert uuid.UUID(body["id"])
    assert body["status"] == "active"
    # The password hash must never appear in the response.
    assert "password" not in body
    assert "hash" not in body


async def test_register_duplicate_email(client: httpx.AsyncClient):
    email = unique_email()
    first = await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert first.status_code == 201
    second = await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"password": PASSWORD},  # missing email
        {"email": unique_email()},  # missing password
        {"email": unique_email(), "password": "short"},  # weak password (< 8)
        {},  # empty payload
    ],
)
async def test_register_invalid_input(client: httpx.AsyncClient, payload: dict):
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    # Raw input values must not be echoed back.
    assert "not-an-email" not in response.text


async def test_register_strips_whitespace_in_email(client: httpx.AsyncClient):
    """Surrounding whitespace is stripped by email validation (normalization)."""
    email = unique_email()
    response = await client.post(
        "/auth/register", json={"email": f" {email} ", "password": PASSWORD}
    )
    assert response.status_code == 201
    assert response.json()["email"] == email


async def test_password_hashed_at_rest(client: httpx.AsyncClient, database_url: str):
    """The database stores an argon2id hash — never the plaintext."""
    from sqlalchemy.ext.asyncio import create_async_engine

    email = unique_email()
    response = await client.post(
        "/auth/register", json={"email": email, "password": "plaintext-not-stored-99"}
    )
    assert response.status_code == 201

    engine = create_async_engine(database_url)
    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT password_hash FROM users WHERE email = :email"),
                    {"email": email},
                )
            ).scalar_one()
    finally:
        await engine.dispose()

    assert row.startswith("$argon2id$")
    assert "plaintext-not-stored-99" not in row


# --- Login ------------------------------------------------------------------


async def test_login_valid(client: httpx.AsyncClient):
    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    response = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == email
    assert "password" not in body["user"]


async def test_login_case_insensitive_email(client: httpx.AsyncClient):
    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    response = await client.post("/auth/login", json={"email": email.upper(), "password": PASSWORD})
    assert response.status_code == 200


async def test_login_wrong_password(client: httpx.AsyncClient):
    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    response = await client.post(
        "/auth/login", json={"email": email, "password": "wrong-password-123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_unknown_email_same_error_as_wrong_password(
    client: httpx.AsyncClient,
):
    """Unknown email and wrong password return the identical generic 401
    (no account enumeration)."""
    unknown = await client.post(
        "/auth/login",
        json={"email": unique_email(), "password": "whatever-password-1"},
    )
    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    wrong_password = await client.post(
        "/auth/login", json={"email": email, "password": "wrong-password-123"}
    )
    assert unknown.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown.json()["error"]["code"] == "invalid_credentials"
    # Identical generic errors (request_id is intentionally unique per request).
    assert unknown.json()["error"] == wrong_password.json()["error"]


async def test_login_never_logs_password(client: httpx.AsyncClient):
    """The password value must not appear in any log record."""
    from structlog.testing import capture_logs

    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    with capture_logs() as logs:
        response = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    dumped = repr(logs)
    assert PASSWORD not in dumped


# --- Session validation (/auth/me) ------------------------------------------


async def test_me_with_valid_token(client: httpx.AsyncClient):
    token, user = await register_and_login(client)
    response = await client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user["id"]
    assert body["email"] == user["email"]
    assert "password" not in body


async def test_me_without_token(client: httpx.AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_me_with_invalid_token(client: httpx.AsyncClient):
    response = await client.get("/auth/me", headers=auth_headers("not-a-real-token-value"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_me_with_malformed_authorization_header(client: httpx.AsyncClient):
    for header in ("garbage-no-bearer", "Bearer", "Basic dXNlcjpwYXNz"):
        response = await client.get("/auth/me", headers={"Authorization": header})
        assert response.status_code == 401, f"{header!r} did not fail safely"
        assert response.json()["error"]["code"] == "unauthorized"


async def test_expired_session_rejected(client: httpx.AsyncClient, database_url: str):
    """An expired session returns 401 session_expired (distinct from unknown)."""
    token, _ = await register_and_login(client)

    # Expire the session directly in the database.
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    try:
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE auth_sessions SET expires_at = :past WHERE token_hash = :th"),
                {
                    "past": datetime.now(UTC) - timedelta(hours=1),
                    "th": hash_token(token),
                },
            )
    finally:
        await engine.dispose()

    response = await client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


# --- Logout -----------------------------------------------------------------


async def test_logout_invalidates_session(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)

    # Token works before logout.
    assert (await client.get("/auth/me", headers=auth_headers(token))).status_code == 200

    response = await client.post("/auth/logout", headers=auth_headers(token))
    assert response.status_code == 200

    # Token is unusable after logout.
    after = await client.get("/auth/me", headers=auth_headers(token))
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "unauthorized"


async def test_logout_requires_authentication(client: httpx.AsyncClient):
    response = await client.post("/auth/logout")
    assert response.status_code == 401


async def test_logout_twice_fails_safely(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    assert (await client.post("/auth/logout", headers=auth_headers(token))).status_code == 200
    second = await client.post("/auth/logout", headers=auth_headers(token))
    assert second.status_code == 401


async def test_other_sessions_survive_logout(client: httpx.AsyncClient):
    """Logging out of one session must not invalidate other sessions."""
    email = unique_email()
    token1, _ = await register_and_login(client, email=email)

    # A second session for the same user (login again, no re-registration).
    login2 = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login2.status_code == 200
    token2 = login2.json()["token"]
    assert token2 != token1

    await client.post("/auth/logout", headers=auth_headers(token1))

    response = await client.get("/auth/me", headers=auth_headers(token2))
    assert response.status_code == 200
