"""Instagram integration tests (Phase 9).

SIMULATOR_ONLY for the Instagram connection/webhook contract: the real
Instagram identifier semantics (Messenger API for Instagram) are
UNKNOWN_META. REAL META API TEST = BLOCKED (no credentials).

Tests cover: the platform abstraction (migration 0009), the Instagram
connection lifecycle via the existing connection API, identity separation
(an Instagram identity never collides with a WhatsApp identity), webhook
ingestion through the existing gateway, and the pipeline E2E (Instagram
event → message → extraction → order).
"""

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from simulator.client import SimulatorClient
from simulator.fixtures import (
    INSTAGRAM_PHONE_NUMBER_ID,
    build_event,
)
from simulator.setup import FIXTURE_TENANT_ID, create_fixture_connection

TEST_SECRET = "simulator-test-secret"


@pytest.fixture()
async def simulator(client: httpx.AsyncClient, database_url: str) -> SimulatorClient:
    """Simulator client bound to the real app, with the fixture connections
    (WhatsApp + Instagram)."""
    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
    finally:
        await engine.dispose()
    return SimulatorClient(base_url="http://testserver", secret=TEST_SECRET)


def unique_sender() -> str:
    return f"ig{uuid.uuid4().hex[:10]}"


async def run_processor(database_url: str, **kwargs):
    """Run the deterministic processor against the database."""
    from app.pipeline.consumer import process_pending_events

    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as db:
            return await process_pending_events(db, **kwargs)
    finally:
        await engine.dispose()


async def register_owner(client: httpx.AsyncClient) -> str:
    """A user with the OWNER membership on the fixture tenant."""
    from sqlalchemy.ext.asyncio import create_async_engine as _cae

    from app.models import Role, TenantMember

    email = f"ig-owner-{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post(
        "/auth/register", json={"email": email, "password": "password-123"}
    )
    assert response.status_code == 201
    user = response.json()

    import os

    database_url = os.environ["DATABASE_URL"]
    engine = _cae(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
            session.add(
                TenantMember(
                    tenant_id=FIXTURE_TENANT_ID,
                    user_id=uuid.UUID(user["id"]),
                    role=Role.OWNER,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()

    login_response = await client.post(
        "/auth/login", json={"email": email, "password": "password-123"}
    )
    assert login_response.status_code == 200
    return login_response.json()["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Connection API (platform-aware) ------------------------------------------


async def test_instagram_connection_status_disconnected(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """The Instagram connection status via the existing API (platform param)."""
    token = await register_owner(client)
    response = await client.get(
        f"/tenants/{FIXTURE_TENANT_ID}/connection",
        params={"platform": "instagram"},
        headers=auth(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "instagram"
    # The fixture connection IS connected (created by the fixture).
    assert body["status"] == "connected"


async def test_instagram_connection_isolated_from_whatsapp(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """The WhatsApp and Instagram connections are DISTINCT records (the
    platform is part of the uniqueness)."""
    token = await register_owner(client)
    whatsapp = await client.get(
        f"/tenants/{FIXTURE_TENANT_ID}/connection",
        params={"platform": "whatsapp"},
        headers=auth(token),
    )
    instagram = await client.get(
        f"/tenants/{FIXTURE_TENANT_ID}/connection",
        params={"platform": "instagram"},
        headers=auth(token),
    )
    assert whatsapp.json()["platform"] == "whatsapp"
    assert instagram.json()["platform"] == "instagram"
    assert whatsapp.json()["id"] != instagram.json()["id"]


async def test_instagram_initiate_idempotent_and_conflict(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """Initiation is idempotent while initiated; a connected Instagram
    connection → 409 conflict."""
    token = await register_owner(client)

    # The fixture Instagram connection is CONNECTED → initiation conflicts.
    response = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/connection/initiate",
        params={"platform": "instagram"},
        headers=auth(token),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert "Instagram" in response.json()["error"]["message"]

    # Disconnect, then initiation succeeds (idempotent).
    disconnect = await client.delete(
        f"/tenants/{FIXTURE_TENANT_ID}/connection",
        params={"platform": "instagram"},
        headers=auth(token),
    )
    assert disconnect.status_code == 200
    assert disconnect.json()["status"] == "disconnected"

    first = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/connection/initiate",
        params={"platform": "instagram"},
        headers=auth(token),
    )
    assert first.status_code == 200
    assert first.json()["platform"] == "instagram"
    assert first.json()["status"] == "initiated"
    # No fake Meta success: the authorization is pending configuration.
    assert "pending" in first.json()["detail"].lower()

    second = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/connection/initiate",
        params={"platform": "instagram"},
        headers=auth(token),
    )
    assert second.status_code == 200  # idempotent


async def test_instagram_connection_requires_owner_role(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """A non-member cannot access the Instagram connection; a member (not
    owner) cannot initiate."""
    from sqlalchemy.ext.asyncio import create_async_engine as _cae

    from app.models import Role, TenantMember

    await register_owner(client)

    # A non-member outsider.
    outsider = f"outsider-{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": outsider, "password": "password-123"})
    outsider_token = (
        await client.post("/auth/login", json={"email": outsider, "password": "password-123"})
    ).json()["token"]

    response = await client.get(
        f"/tenants/{FIXTURE_TENANT_ID}/connection",
        params={"platform": "instagram"},
        headers=auth(outsider_token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

    # A MEMBER (not owner) of the fixture tenant.
    member_email = f"ig-member-{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": member_email, "password": "password-123"})
    member_token = (
        await client.post(
            "/auth/login",
            json={"email": member_email, "password": "password-123"},
        )
    ).json()["token"]

    import os

    database_url = os.environ["DATABASE_URL"]
    engine = _cae(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
            # Get the member's user id.

            user_result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": member_email},
            )
            user_id = user_result.scalar_one()
            session.add(
                TenantMember(tenant_id=FIXTURE_TENANT_ID, user_id=user_id, role=Role.MEMBER)
            )
            await session.commit()
    finally:
        await engine.dispose()

    # The member can READ the connection status…
    read = await client.get(
        f"/tenants/{FIXTURE_TENANT_ID}/connection",
        params={"platform": "instagram"},
        headers=auth(member_token),
    )
    assert read.status_code == 200

    # …but cannot initiate (OWNER only).
    initiate = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/connection/initiate",
        params={"platform": "instagram"},
        headers=auth(member_token),
    )
    assert initiate.status_code == 403


async def test_instagram_connection_forged_tenant_id(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """A forged tenant id → 404 (no existence inference)."""
    token = await register_owner(client)
    response = await client.get(
        f"/tenants/{uuid.uuid4()}/connection",
        params={"platform": "instagram"},
        headers=auth(token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- Webhook ingestion (the existing gateway, platform-aware) -------------------


async def test_instagram_event_via_the_instagram_route(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """An Instagram event submitted to /webhooks/instagram → accepted by the
    existing gateway (the payload's platform drives the resolution)."""
    sender = unique_sender()
    message_id = f"wamid.ig-{uuid.uuid4().hex[:8]}"

    from simulator.fixtures import serialize, signature_for

    payload = build_event(
        message_id,
        sender=sender,
        text="I want to order 2 shirts",
        phone_number_id=INSTAGRAM_PHONE_NUMBER_ID,
        waba_id=None,
    )
    payload["platform"] = "instagram"
    raw = serialize(payload)
    headers = {
        "Content-Type": "application/json",
        "X-Floww-Simulator-Signature": signature_for(TEST_SECRET, raw),
    }
    response = await client.post("/webhooks/instagram", content=raw, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    # Duplicate delivery (same bytes) → duplicate, one event.
    duplicate = await client.post("/webhooks/instagram", content=raw, headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "duplicate"


async def test_instagram_event_via_the_whatsapp_route_also_works(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """The route is cosmetic: the payload's platform field drives the
    resolution (an Instagram event via /webhooks/whatsapp still resolves to
    the Instagram connection)."""
    sender = unique_sender()
    message_id = f"wamid.ig-{uuid.uuid4().hex[:8]}"
    payload = build_event(
        message_id,
        sender=sender,
        text="hello",
        phone_number_id=INSTAGRAM_PHONE_NUMBER_ID,
        waba_id=None,
    )
    payload["platform"] = "instagram"
    response = await simulator.submit(payload, client=client)
    assert response.status_code == 202


async def test_instagram_event_unknown_connection_rejected(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """An Instagram event for an unmapped connection → 404."""
    from simulator.fixtures import UNMAPPED_PHONE_NUMBER_ID

    payload = build_event(
        f"wamid.ig-{uuid.uuid4().hex[:8]}",
        sender=unique_sender(),
        text="hello",
        phone_number_id=UNMAPPED_PHONE_NUMBER_ID,
        waba_id=None,
    )
    payload["platform"] = "instagram"
    response = await simulator.submit(payload, client=client)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_connection"


async def test_instagram_event_requires_the_right_platform_connection(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """An Instagram-platform event must NOT resolve to the WhatsApp
    connection (the platform boundary is part of the resolution)."""
    # The WhatsApp fixture's phone_number_id with platform=instagram: no
    # Instagram connection maps to it → 404 (not the WhatsApp connection).
    from simulator.fixtures import CONNECTION_PHONE_NUMBER_ID

    payload = build_event(
        f"wamid.ig-{uuid.uuid4().hex[:8]}",
        sender=unique_sender(),
        text="hello",
        phone_number_id=CONNECTION_PHONE_NUMBER_ID,
        waba_id=None,
    )
    payload["platform"] = "instagram"
    response = await simulator.submit(payload, client=client)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_connection"


# --- Identity / pipeline E2E ------------------------------------------------------


async def test_instagram_identity_separate_from_whatsapp_identity(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """tenant + INSTAGRAM + external_user_id is a DISTINCT identity from
    tenant + WHATSAPP + the same external_user_id."""
    external_user_id = f"user-{uuid.uuid4().hex[:10]}"

    # A WhatsApp event and an Instagram event from the SAME external id.
    await simulator.submit(
        build_event(
            f"wamid.ig-{uuid.uuid4().hex[:8]}",
            sender=external_user_id,
            text="hello from whatsapp",
            phone_number_id="555666444",
            waba_id="999888777",
        ),
        client=client,
    )
    ig_payload = build_event(
        f"wamid.ig-{uuid.uuid4().hex[:8]}",
        sender=external_user_id,
        text="hello from instagram",
        phone_number_id=INSTAGRAM_PHONE_NUMBER_ID,
        waba_id=None,
    )
    ig_payload["platform"] = "instagram"
    await simulator.submit(ig_payload, client=client)

    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            identities = (
                await conn.execute(
                    text(
                        "SELECT platform, count(*) FROM customer_platform_identities "
                        "WHERE external_user_id = :u GROUP BY platform"
                    ),
                    {"u": external_user_id},
                )
            ).fetchall()
    finally:
        await engine.dispose()

    identity_map = {row[0]: row[1] for row in identities}
    # TWO distinct identities: one per platform (never merged).
    assert identity_map.get("whatsapp") == 1
    assert identity_map.get("instagram") == 1


async def test_instagram_event_flows_through_the_full_pipeline(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """Instagram event → message → extraction candidate → order — the
    existing pipeline (no parallel architecture)."""
    sender = unique_sender()
    message_id = f"wamid.ig-{uuid.uuid4().hex[:8]}"
    ig_payload = build_event(
        message_id,
        sender=sender,
        text="I want to order 2 large blue shirts",
        phone_number_id=INSTAGRAM_PHONE_NUMBER_ID,
        waba_id=None,
    )
    ig_payload["platform"] = "instagram"
    response = await simulator.submit(ig_payload, client=client)
    assert response.status_code == 202

    result = await run_processor(database_url)
    assert result.processed == 1

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            # The message exists on the INSTAGRAM connection's conversation.
            row = (
                await conn.execute(
                    text(
                        "SELECT c.status, i.product, i.quantity "
                        "FROM messages m "
                        "JOIN conversations c ON c.id = m.conversation_id "
                        "LEFT JOIN order_extraction_candidates cand ON cand.message_id = m.id "
                        "LEFT JOIN orders o ON o.extraction_candidate_id = cand.id "
                        "LEFT JOIN order_items i ON i.order_id = o.id "
                        "WHERE m.external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).first()
            # The platform chain: the conversation's connection is Instagram.
            platform_row = (
                await conn.execute(
                    text(
                        "SELECT pc.platform FROM messages m "
                        "JOIN conversations c ON c.id = m.conversation_id "
                        "JOIN platform_connections pc ON pc.id = c.connection_id "
                        "WHERE m.external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).first()
    finally:
        await engine.dispose()

    assert platform_row is not None
    assert platform_row[0] == "instagram"  # the Instagram connection's conversation
    assert row is not None
    assert row[0] == "open"
    # The extraction + order were created through the existing pipeline.
    assert row[1] == "shirt"
    assert row[2] == 2


# --- Concurrency ----------------------------------------------------------------


async def test_instagram_concurrent_duplicates_create_one_event(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """Concurrent duplicate Instagram events: exactly one accepted, the rest
    duplicates; one event in the database."""
    sender = unique_sender()
    message_id = f"wamid.ig-{uuid.uuid4().hex[:8]}"
    payload = build_event(
        message_id,
        sender=sender,
        text="hello",
        phone_number_id=INSTAGRAM_PHONE_NUMBER_ID,
        waba_id=None,
    )
    payload["platform"] = "instagram"

    responses = await asyncio.gather(
        *[simulator.submit(payload, client=client) for _ in range(5)],
        return_exceptions=True,
    )
    statuses = [r.status_code for r in responses if hasattr(r, "status_code")]
    assert len(statuses) == 5
    assert statuses.count(202) == 1
    assert statuses.count(200) == 4

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            count = (
                await conn.execute(
                    text("SELECT count(*) FROM webhook_events WHERE external_event_id = :eid"),
                    {"eid": message_id},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert count == 1
