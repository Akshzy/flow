"""Tenant endpoint tests: creation, membership, access, role restrictions.

All flows run against the real app + PostgreSQL via the test client.
Authorization must be enforced server-side (404 missing, 403 forbidden).
"""

import uuid

import httpx
import pytest
from sqlalchemy import text

from tests.helpers import auth_headers, create_tenant, register_and_login

# --- Creation ---------------------------------------------------------------


async def test_create_tenant_authenticated(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    response = await client.post("/tenants", json={"name": "Shop One"}, headers=auth_headers(token))
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Shop One"
    assert uuid.UUID(body["id"])
    assert body["role"] == "owner"


async def test_create_tenant_unauthenticated(client: httpx.AsyncClient):
    response = await client.post("/tenants", json={"name": "Sneaky Shop"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},  # empty name
        {"name": "x" * 201},  # too long
        {},  # missing name
        {"name": "Shop", "role": "owner"},  # extra fields ignored, still valid
    ],
)
async def test_create_tenant_invalid_input(client: httpx.AsyncClient, payload: dict):
    token, _ = await register_and_login(client)
    response = await client.post("/tenants", json=payload, headers=auth_headers(token))
    if payload == {"name": "Shop", "role": "owner"}:
        # Unknown fields are ignored (no mass assignment); creation succeeds
        # and the role is assigned server-side.
        assert response.status_code == 201
        assert response.json()["role"] == "owner"
    else:
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


async def test_owner_membership_created_in_db(client: httpx.AsyncClient, database_url: str):
    token, user = await register_and_login(client)
    tenant = await create_tenant(client, token, "Shop DB Check")

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT role FROM tenant_members WHERE tenant_id = :t AND user_id = :u"),
                    {"t": tenant["id"], "u": user["id"]},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert row == "owner"


# --- Listing (tenant-scoped) ------------------------------------------------


async def test_list_tenants_returns_only_my_tenants(client: httpx.AsyncClient):
    """The list endpoint must never return another user's tenants."""
    token_a, _ = await register_and_login(client)
    token_b, _ = await register_and_login(client)

    tenant_a = await create_tenant(client, token_a, "A's Shop")
    tenant_b = await create_tenant(client, token_b, "B's Shop")

    list_a = (await client.get("/tenants", headers=auth_headers(token_a))).json()
    list_b = (await client.get("/tenants", headers=auth_headers(token_b))).json()

    assert [t["id"] for t in list_a] == [tenant_a["id"]]
    assert tenant_b["id"] not in [t["id"] for t in list_a]
    assert [t["id"] for t in list_b] == [tenant_b["id"]]
    assert tenant_a["id"] not in [t["id"] for t in list_b]


async def test_list_tenants_requires_auth(client: httpx.AsyncClient):
    response = await client.get("/tenants")
    assert response.status_code == 401


# --- Retrieval --------------------------------------------------------------


async def test_get_tenant_as_member(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "My Shop")
    response = await client.get(f"/tenants/{tenant['id']}", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["id"] == tenant["id"]
    assert response.json()["role"] == "owner"


async def test_get_tenant_missing(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    response = await client.get(f"/tenants/{uuid.uuid4()}", headers=auth_headers(token))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_tenant_invalid_uuid(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    response = await client.get("/tenants/not-a-uuid", headers=auth_headers(token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --- Rename (OWNER only) ----------------------------------------------------


async def test_rename_tenant_as_owner(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Old Name")
    response = await client.patch(
        f"/tenants/{tenant['id']}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"

    # The change is persisted.
    fetched = await client.get(f"/tenants/{tenant['id']}", headers=auth_headers(token))
    assert fetched.json()["name"] == "New Name"


async def test_rename_tenant_missing(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    response = await client.patch(
        f"/tenants/{uuid.uuid4()}", json={"name": "X"}, headers=auth_headers(token)
    )
    assert response.status_code == 404


@pytest.mark.parametrize("payload", [{"name": ""}, {}, {"name": "y" * 201}])
async def test_rename_tenant_invalid_input(client: httpx.AsyncClient, payload: dict):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Stable Name")
    response = await client.patch(
        f"/tenants/{tenant['id']}", json=payload, headers=auth_headers(token)
    )
    assert response.status_code == 422


# --- Deletion (OWNER only) --------------------------------------------------


async def test_delete_tenant_as_owner(client: httpx.AsyncClient, database_url: str):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Doomed Shop")
    response = await client.delete(f"/tenants/{tenant['id']}", headers=auth_headers(token))
    assert response.status_code == 204

    # The tenant is gone (404 for the former owner as well).
    after = await client.get(f"/tenants/{tenant['id']}", headers=auth_headers(token))
    assert after.status_code == 404
    assert after.json()["error"]["code"] == "not_found"

    # Memberships were removed by the database cascade.
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            count = (
                await conn.execute(
                    text("SELECT count(*) FROM tenant_members WHERE tenant_id = :t"),
                    {"t": tenant["id"]},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert count == 0


async def test_delete_tenant_missing(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    response = await client.delete(f"/tenants/{uuid.uuid4()}", headers=auth_headers(token))
    assert response.status_code == 404


async def test_delete_tenant_unauthenticated(client: httpx.AsyncClient):
    token, _ = await register_and_login(client)
    tenant = await create_tenant(client, token, "Protected Shop")
    response = await client.delete(f"/tenants/{tenant['id']}")
    assert response.status_code == 401
    # The tenant still exists.
    still_there = await client.get(f"/tenants/{tenant['id']}", headers=auth_headers(token))
    assert still_there.status_code == 200


# --- Role model (database-level validation) ---------------------------------


async def test_invalid_role_rejected_by_database(client: httpx.AsyncClient, database_url: str):
    """The CHECK constraint rejects role values outside owner/member."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine

    token, user = await register_and_login(client)
    tenant = await create_tenant(client, token, "Role Check Shop")

    engine = create_async_engine(database_url)
    try:
        from sqlalchemy import text as sa_text

        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    sa_text(
                        "INSERT INTO tenant_members (id, tenant_id, user_id, role) "
                        "VALUES (gen_random_uuid(), :t, :u, 'admin')"
                    ),
                    {"t": tenant["id"], "u": user["id"]},
                )
    finally:
        await engine.dispose()
