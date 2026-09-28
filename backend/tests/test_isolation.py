"""Tenant isolation tests — the core Phase 2 security requirement.

Proves (behavior, not implementation details):

- User A → Tenant A: ALLOWED
- User B → Tenant B: ALLOWED
- User A → Tenant B: DENIED (403) for GET/PATCH/DELETE
- User B → Tenant A: DENIED (403)
- Direct-object-ID attack: knowing another tenant's UUID is not sufficient
- Role restrictions: MEMBER can read but not modify/delete
- List endpoints only ever return the caller's tenants
- Data-layer (database) tenant scoping: IDOR-style checks
"""

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.models import Tenant, TenantMember
from tests.helpers import auth_headers, create_tenant, register_and_login


@pytest.fixture()
async def isolated_world(client: httpx.AsyncClient, database_url: str):
    """Two owner users, one plain member, two tenants.

    - user_a: OWNER of tenant_a
    - user_b: OWNER of tenant_b
    - user_c: MEMBER of tenant_a
    """
    token_a, user_a = await register_and_login(client)
    token_b, user_b = await register_and_login(client)
    token_c, user_c = await register_and_login(client)

    tenant_a = await create_tenant(client, token_a, "Tenant A Business")
    tenant_b = await create_tenant(client, token_b, "Tenant B Business")

    # user_c becomes a plain MEMBER of tenant_a via the owner (A) — no
    # membership-creation endpoint exists, so the membership is created
    # directly through the same DB layer the application uses.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with factory() as session:
            from app.models import Role

            membership = TenantMember(
                tenant_id=uuid.UUID(tenant_a["id"]),
                user_id=uuid.UUID(user_c["id"]),
                role=Role.MEMBER,
            )
            session.add(membership)
            await session.commit()
    finally:
        await engine.dispose()

    return {
        "token_a": token_a,
        "token_b": token_b,
        "token_c": token_c,
        "user_a": user_a,
        "user_b": user_b,
        "user_c": user_c,
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
    }


# --- Allowed access ---------------------------------------------------------


async def test_owner_a_accesses_tenant_a(client: httpx.AsyncClient, isolated_world):
    w = isolated_world
    response = await client.get(
        f"/tenants/{w['tenant_a']['id']}", headers=auth_headers(w["token_a"])
    )
    assert response.status_code == 200
    assert response.json()["id"] == w["tenant_a"]["id"]


async def test_owner_b_accesses_tenant_b(client: httpx.AsyncClient, isolated_world):
    w = isolated_world
    response = await client.get(
        f"/tenants/{w['tenant_b']['id']}", headers=auth_headers(w["token_b"])
    )
    assert response.status_code == 200
    assert response.json()["id"] == w["tenant_b"]["id"]


# --- Cross-tenant access: DENIED ---------------------------------------------


@pytest.mark.parametrize(
    "method,payload",
    [
        ("get", None),
        ("patch", {"name": "Hijacked Name"}),
        ("delete", None),
    ],
)
async def test_user_a_cannot_access_tenant_b(
    client: httpx.AsyncClient, isolated_world, method: str, payload
):
    """User A knows Tenant B's ID but must not retrieve or modify it."""
    w = isolated_world
    request = getattr(client, method)
    kwargs = {"headers": auth_headers(w["token_a"])}
    if payload is not None:
        kwargs["json"] = payload
    response = await request(f"/tenants/{w['tenant_b']['id']}", **kwargs)

    assert response.status_code == 403, f"cross-tenant {method} was not blocked"
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(
    "method,payload",
    [
        ("get", None),
        ("patch", {"name": "Hijacked Name"}),
        ("delete", None),
    ],
)
async def test_user_b_cannot_access_tenant_a(
    client: httpx.AsyncClient, isolated_world, method: str, payload
):
    w = isolated_world
    request = getattr(client, method)
    kwargs = {"headers": auth_headers(w["token_b"])}
    if payload is not None:
        kwargs["json"] = payload
    response = await request(f"/tenants/{w['tenant_a']['id']}", **kwargs)

    assert response.status_code == 403, f"cross-tenant {method} was not blocked"
    assert response.json()["error"]["code"] == "forbidden"


async def test_cross_tenant_modification_is_persistently_blocked(
    client: httpx.AsyncClient, isolated_world
):
    """After a blocked cross-tenant rename, Tenant B keeps its original name."""
    w = isolated_world
    await client.patch(
        f"/tenants/{w['tenant_b']['id']}",
        json={"name": "Hijacked Name"},
        headers=auth_headers(w["token_a"]),
    )
    response = await client.get(
        f"/tenants/{w['tenant_b']['id']}", headers=auth_headers(w["token_b"])
    )
    assert response.status_code == 200
    assert response.json()["name"] == w["tenant_b"]["name"]


async def test_direct_object_id_attack_with_forged_uuid(client: httpx.AsyncClient, isolated_world):
    """A random UUID (object-ID probing) must not bypass authorization."""
    w = isolated_world
    response = await client.get(f"/tenants/{uuid.uuid4()}", headers=auth_headers(w["token_a"]))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- Role restrictions --------------------------------------------------------


async def test_member_can_read_tenant(client: httpx.AsyncClient, isolated_world):
    w = isolated_world
    response = await client.get(
        f"/tenants/{w['tenant_a']['id']}", headers=auth_headers(w["token_c"])
    )
    assert response.status_code == 200
    assert response.json()["role"] == "member"


@pytest.mark.parametrize(
    "method,payload",
    [
        ("patch", {"name": "Member Renamed"}),
        ("delete", None),
    ],
)
async def test_member_cannot_modify_or_delete_tenant(
    client: httpx.AsyncClient, isolated_world, method: str, payload
):
    w = isolated_world
    request = getattr(client, method)
    kwargs = {"headers": auth_headers(w["token_c"])}
    if payload is not None:
        kwargs["json"] = payload
    response = await request(f"/tenants/{w['tenant_a']['id']}", **kwargs)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_member_cannot_access_other_tenants(client: httpx.AsyncClient, isolated_world):
    w = isolated_world
    response = await client.get(
        f"/tenants/{w['tenant_b']['id']}", headers=auth_headers(w["token_c"])
    )
    assert response.status_code == 403


# --- List endpoints are tenant-scoped -----------------------------------------


async def test_lists_only_return_the_callers_tenants(client: httpx.AsyncClient, isolated_world):
    w = isolated_world
    list_a = (await client.get("/tenants", headers=auth_headers(w["token_a"]))).json()
    list_b = (await client.get("/tenants", headers=auth_headers(w["token_b"]))).json()
    list_c = (await client.get("/tenants", headers=auth_headers(w["token_c"]))).json()

    assert [t["id"] for t in list_a] == [w["tenant_a"]["id"]]
    assert [t["id"] for t in list_b] == [w["tenant_b"]["id"]]
    assert [t["id"] for t in list_c] == [w["tenant_a"]["id"]]  # member of A only


# --- Database-level isolation (IDOR checks at the data layer) ------------------


async def test_data_layer_membership_lookup_is_user_scoped(
    client: httpx.AsyncClient, isolated_world, database_url: str
):
    """Querying memberships for user A must never return user B's rows."""
    w = isolated_world
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with factory() as session:
            result = await session.execute(
                select(TenantMember).where(TenantMember.user_id == uuid.UUID(w["user_a"]["id"]))
            )
            rows = result.scalars().all()
            assert [str(m.tenant_id) for m in rows] == [w["tenant_a"]["id"]]

            # IDOR-style: user A's user_id combined with tenant B's id must
            # match nothing.
            result = await session.execute(
                select(TenantMember).where(
                    TenantMember.user_id == uuid.UUID(w["user_a"]["id"]),
                    TenantMember.tenant_id == uuid.UUID(w["tenant_b"]["id"]),
                )
            )
            assert result.scalar_one_or_none() is None
    finally:
        await engine.dispose()


async def test_data_layer_tenant_lookup_cannot_leak_other_tenants(
    client: httpx.AsyncClient, isolated_world, database_url: str
):
    """A tenant-scoped lookup for a tenant the user does not belong to
    returns nothing at the data layer (same predicate the API enforces)."""
    w = isolated_world
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with factory() as session:
            result = await session.execute(
                select(Tenant)
                .join(TenantMember, TenantMember.tenant_id == Tenant.id)
                .where(
                    TenantMember.user_id == uuid.UUID(w["user_b"]["id"]),
                    Tenant.id == uuid.UUID(w["tenant_a"]["id"]),
                )
            )
            assert result.scalar_one_or_none() is None
    finally:
        await engine.dispose()


async def test_deleted_tenant_revokes_access(client: httpx.AsyncClient):
    """Deleting a tenant revokes access for everyone (owner included)."""
    # Sacrificial tenant created and deleted by its own owner.
    token_s, _ = await register_and_login(client)
    sacrificial = await create_tenant(client, token_s, "Sacrificial Shop")

    response = await client.delete(f"/tenants/{sacrificial['id']}", headers=auth_headers(token_s))
    assert response.status_code == 204

    after = await client.get(f"/tenants/{sacrificial['id']}", headers=auth_headers(token_s))
    assert after.status_code == 404
