"""WhatsApp connection API tests (tenant-scoped, Phase 4).

All flows run against the real app + PostgreSQL via the test client.
Connection responses must never include credential material; tenant
isolation must be enforced server-side.
"""

import uuid

import httpx
import pytest

from tests.helpers import auth_headers, create_tenant, register_and_login

# --- Status -------------------------------------------------------------------


async def test_status_initially_disconnected(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Fresh Shop")
    response = await client.get(f"/tenants/{tenant['id']}/connection", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disconnected"
    assert body["platform"] == "whatsapp"
    assert body["id"] is None


async def test_status_requires_authentication(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Auth Shop")
    response = await client.get(f"/tenants/{tenant['id']}/connection")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_status_invalid_token(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Auth Shop 2")
    response = await client.get(
        f"/tenants/{tenant['id']}/connection",
        headers=auth_headers("bogus-token-value"),
    )
    assert response.status_code == 401


# --- Initiation -----------------------------------------------------------------


async def test_initiate_creates_initiated_record(client: httpx.AsyncClient, database_url: str):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Init Shop")
    response = await client.post(
        f"/tenants/{tenant['id']}/connection/initiate",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "whatsapp"
    assert body["status"] == "initiated"
    # The response states the Meta authorization step is pending — no fake
    # Meta success is claimed.
    assert body["detail"]
    assert "pending" in body["detail"].lower()

    # The record exists in the database, tenant-owned.
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text

            row = (
                await conn.execute(
                    text(
                        "SELECT status, tenant_id FROM platform_connections "
                        "ORDER BY created_at DESC LIMIT 1"
                    )
                )
            ).first()
            assert row is not None
            assert row[0] == "initiated"
            assert str(row[1]) == tenant["id"]
    finally:
        await engine.dispose()


async def test_initiate_is_idempotent_while_initiated(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Idempotent Shop")
    first = await client.post(
        f"/tenants/{tenant['id']}/connection/initiate", headers=auth_headers(token)
    )
    second = await client.post(
        f"/tenants/{tenant['id']}/connection/initiate", headers=auth_headers(token)
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "initiated"


async def test_initiate_requires_owner_role(client: httpx.AsyncClient, database_url: str):
    """A plain MEMBER cannot start the connection lifecycle."""
    owner_token, _ = await register_and_login(client)
    member_token, member = await register_and_login(client)
    tenant = await create_tenant(client, owner_token, "Role Shop")

    # Make the member a MEMBER of the tenant (data-layer operation).
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with factory() as session:
            from app.models import Role, TenantMember

            session.add(
                TenantMember(
                    tenant_id=uuid.UUID(tenant["id"]),
                    user_id=uuid.UUID(member["id"]),
                    role=Role.MEMBER,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()

    response = await client.post(
        f"/tenants/{tenant['id']}/connection/initiate",
        headers=auth_headers(member_token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_initiate_requires_authentication(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Unauth Init")
    response = await client.post(f"/tenants/{tenant['id']}/connection/initiate")
    assert response.status_code == 401


# --- Disconnect -----------------------------------------------------------------


async def test_disconnect_by_owner(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Disconnect Shop")
    await client.post(f"/tenants/{tenant['id']}/connection/initiate", headers=auth_headers(token))
    response = await client.delete(
        f"/tenants/{tenant['id']}/connection", headers=auth_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"

    # Status endpoint reports disconnected afterwards.
    after = await client.get(f"/tenants/{tenant['id']}/connection", headers=auth_headers(token))
    assert after.json()["status"] == "disconnected"


async def test_disconnect_with_no_active_connection(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "No Connection Shop")
    response = await client.delete(
        f"/tenants/{tenant['id']}/connection", headers=auth_headers(token)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_disconnect_requires_owner_role(client: httpx.AsyncClient):
    """A non-member cannot disconnect another tenant's connection."""
    owner_token, _ = await register_and_login(client)
    other_token, _ = await register_and_login(client)
    tenant = await create_tenant(client, owner_token, "Disconnect Guard")
    await client.post(
        f"/tenants/{tenant['id']}/connection/initiate",
        headers=auth_headers(owner_token),
    )
    response = await client.delete(
        f"/tenants/{tenant['id']}/connection", headers=auth_headers(other_token)
    )
    assert response.status_code == 403

    # The connection is unaffected.
    still = await client.get(
        f"/tenants/{tenant['id']}/connection", headers=auth_headers(owner_token)
    )
    assert still.json()["status"] == "initiated"


# --- Tenant isolation ------------------------------------------------------------


async def test_tenant_a_cannot_access_tenant_b_connection(
    client: httpx.AsyncClient,
):
    token_a, _ = await register_and_login(client)
    token_b, _ = await register_and_login(client)
    tenant_a = await create_tenant(client, token_a, "Isolation A")
    tenant_b = await create_tenant(client, token_b, "Isolation B")

    await client.post(
        f"/tenants/{tenant_b['id']}/connection/initiate",
        headers=auth_headers(token_b),
    )

    # A knows B's tenant id but cannot read B's connection status.
    response = await client.get(
        f"/tenants/{tenant_b['id']}/connection", headers=auth_headers(token_a)
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

    # A cannot initiate/modify B's connection either.
    modify = await client.post(
        f"/tenants/{tenant_b['id']}/connection/initiate",
        headers=auth_headers(token_a),
    )
    assert modify.status_code == 403

    # A cannot delete B's connection.
    delete = await client.delete(
        f"/tenants/{tenant_b['id']}/connection", headers=auth_headers(token_a)
    )
    assert delete.status_code == 403

    # A's own tenant access is unaffected: the status endpoint works for the
    # caller's own tenant while B's is denied.
    own = await client.get(f"/tenants/{tenant_a['id']}/connection", headers=auth_headers(token_a))
    assert own.status_code == 200
    assert own.json()["status"] == "disconnected"


async def test_forged_tenant_id_does_not_bypass(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    for method, path in (
        ("get", "/connection"),
        ("post", "/connection/initiate"),
        ("delete", "/connection"),
    ):
        request = getattr(client, method)
        response = await request(f"/tenants/{uuid.uuid4()}{path}", headers=auth_headers(token))
        assert response.status_code == 404, f"{method} did not fail safely"


# --- Credential security -----------------------------------------------------------


async def test_connection_responses_never_contain_credentials(
    client: httpx.AsyncClient, database_url: str
):
    """Credential material never appears in connection API responses."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    token, user = await register_and_login(client)
    tenant = await create_tenant(client, token, "Credential Safety")

    # Store a connection with (deterministic test) credential material via
    # the adapter's connect() — the same path the real flow will use.
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        from cryptography.fernet import Fernet

        from app.credential_store import CredentialStore
        from app.meta import MetaConnectionService

        service = MetaConnectionService(CredentialStore(Fernet.generate_key().decode()))
        async with factory() as session:
            connection = service.initiate(uuid.UUID(tenant["id"]), uuid.UUID(user["id"]))
            service.connect(
                connection,
                waba_id="999888777",
                phone_number_id="555666444",
                credentials={"access_token": "very-secret-test-token-4"},
            )
            session.add(connection)
            await session.commit()
    finally:
        await engine.dispose()

    response = await client.get(f"/tenants/{tenant['id']}/connection", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    # Identifier metadata is visible (not secrets); credential material is not.
    assert body["status"] == "connected"
    assert body["waba_id"] == "999888777"
    # The plaintext token and any credential field must not appear.
    assert "very-secret-test-token-4" not in response.text
    assert "credentials" not in response.text
    assert "access_token" not in response.text


async def test_connection_logs_never_contain_credentials(client: httpx.AsyncClient):
    from structlog.testing import capture_logs

    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Log Safety")
    with capture_logs() as logs:
        await client.post(
            f"/tenants/{tenant['id']}/connection/initiate",
            headers=auth_headers(token),
        )
    dumped = repr(logs)
    assert "Bearer" not in dumped
    assert token not in dumped  # the session token is never logged


# --- Duplicate connection (data-layer) ----------------------------------------------


async def test_duplicate_active_connection_rejected_by_database(
    client: httpx.AsyncClient, database_url: str
):
    """The partial unique index allows only ONE active connection per
    (tenant, platform); disconnected history rows don't count."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    token, user = await register_and_login(client)
    tenant = await create_tenant(client, token, "Duplicate Shop")

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with factory() as session:
            from app.meta import MetaConnectionService

            service = MetaConnectionService(None)
            first = service.initiate(uuid.UUID(tenant["id"]), uuid.UUID(user["id"]))
            session.add(first)
            await session.commit()

            # A second ACTIVE connection for the same tenant+platform violates
            # the partial unique index.
            second = service.initiate(uuid.UUID(tenant["id"]), uuid.UUID(user["id"]))
            session.add(second)
            from sqlalchemy.exc import IntegrityError

            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()
