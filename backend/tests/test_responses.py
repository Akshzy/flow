"""Controlled seller response tests (Phase 10).

Flow: simulator → HTTP → event → processor → candidate + order → the seller
confirms the order (the API) → the response draft → approve → send.

The lifecycle: DRAFT → APPROVED → SENT; FAILED (a send failure — bounded
retry). The seller's explicit approval is the ONLY path to send; the
production send is UNKNOWN_META (the adapter refuses; a test double is
injected for the send-success paths).
"""

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from simulator.client import SimulatorClient
from simulator.fixtures import build_event
from simulator.setup import FIXTURE_TENANT_ID, create_fixture_connection

TEST_SECRET = "simulator-test-secret"


@pytest.fixture()
async def simulator(client: httpx.AsyncClient, database_url: str) -> SimulatorClient:
    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
    finally:
        await engine.dispose()
    return SimulatorClient(base_url="http://testserver", secret=TEST_SECRET)


def unique_sender() -> str:
    return f"1555{uuid.uuid4().hex[:8]}000"


async def run_processor(database_url: str, **kwargs):
    from app.pipeline.consumer import process_pending_events

    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as db:
            return await process_pending_events(db, **kwargs)
    finally:
        await engine.dispose()


async def register_owner_for_fixture(client: httpx.AsyncClient) -> str:
    """A user with the OWNER membership on the fixture tenant."""
    from app.models import Role, TenantMember

    email = f"p10-owner-{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": email, "password": "password-123"})
    import os

    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": email},
            )
            user_id = result.scalar_one()
            session.add(TenantMember(tenant_id=FIXTURE_TENANT_ID, user_id=user_id, role=Role.OWNER))
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


async def _confirmed_order_id(
    client: httpx.AsyncClient,
    simulator: SimulatorClient,
    database_url: str,
    sender: str,
    token: str,
) -> str:
    """Create an order via the pipeline and confirm it via the API."""
    message_id = f"wamid.p10-{uuid.uuid4().hex[:8]}"
    response = await simulator.submit(
        build_event(message_id, sender=sender, text="I want 2 large blue shirts"),
        client=client,
    )
    assert response.status_code == 202
    await run_processor(database_url)

    import psycopg

    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT o.id, c.id FROM orders o "
            "JOIN customers cu ON cu.id = o.customer_id "
            "JOIN customer_platform_identities i ON i.customer_id = cu.id "
            "JOIN order_extraction_candidates c ON c.id = o.extraction_candidate_id "
            "WHERE i.external_user_id = %s",
            (sender,),
        )
        row = cur.fetchone()
        assert row is not None, "the order was not created"
        order_id = str(row[0])
    conn.close()

    confirm = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/orders/{order_id}/confirm", headers=auth(token)
    )
    assert confirm.status_code == 200
    return order_id


async def _conversation_id_for_order(database_url: str, order_id: str) -> str:
    import psycopg

    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT conversation_id FROM orders WHERE id = %s", (uuid.UUID(order_id),))
        row = cur.fetchone()
    conn.close()
    assert row is not None
    return str(row[0])


# --- Intent classification + response creation --------------------------------


async def test_response_created_for_confirmed_order(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """A confirmed order → the response draft (ai_suggested, deterministic
    content from the order's actual items)."""
    token = await register_owner_for_fixture(client)
    sender = unique_sender()
    order_id = await _confirmed_order_id(client, simulator, database_url, sender, token)
    conversation_id = await _conversation_id_for_order(database_url, order_id)

    response = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/conversations/{conversation_id}/responses",
        headers=auth(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "order_confirmation"
    assert body["origin"] == "ai_suggested"
    assert body["status"] == "draft"
    # The content is built from the order's actual items — never invented.
    assert "2x shirt" in body["content"]
    assert "large" not in body["content"] or "shirt" in body["content"]


async def test_response_creation_requires_owner(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """A non-owner member cannot create response drafts."""
    from app.models import Role, TenantMember

    owner_token = await register_owner_for_fixture(client)
    sender = unique_sender()
    order_id = await _confirmed_order_id(client, simulator, database_url, sender, owner_token)
    conversation_id = await _conversation_id_for_order(database_url, order_id)

    # A MEMBER of the fixture tenant.
    member_email = f"p10-member-{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": member_email, "password": "password-123"})
    member_token = (
        await client.post("/auth/login", json={"email": member_email, "password": "password-123"})
    ).json()["token"]

    import os

    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
            user_id = (
                await session.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": member_email},
                )
            ).scalar_one()
            session.add(
                TenantMember(tenant_id=FIXTURE_TENANT_ID, user_id=user_id, role=Role.MEMBER)
            )
            await session.commit()
    finally:
        await engine.dispose()

    response = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/conversations/{conversation_id}/responses",
        headers=auth(member_token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_no_response_for_unconfirmed_order(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """A conversation WITHOUT a confirmed order → no response (the state
    cannot back it; controlled 422)."""
    token = await register_owner_for_fixture(client)
    sender = unique_sender()
    message_id = f"wamid.p10-{uuid.uuid4().hex[:8]}"
    await simulator.submit(
        build_event(message_id, sender=sender, text="I want 2 shirts"), client=client
    )
    await run_processor(database_url)

    import psycopg

    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT cv.id FROM conversations cv "
            "JOIN customer_platform_identities i ON i.customer_id = cv.customer_id "
            "WHERE i.external_user_id = %s",
            (sender,),
        )
        row = cur.fetchone()
    conn.close()
    assert row is not None
    conversation_id = str(row[0])

    response = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/conversations/{conversation_id}/responses",
        headers=auth(token),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_response_available"


# --- Approval + send workflow --------------------------------------------------


async def test_approval_is_explicit_and_send_is_blocked_until_verified(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """DRAFT → APPROVED (explicit seller action); the production send is
    UNKNOWN_META → a controlled failure (never a fake success); the response
    stays APPROVED (retryable)."""
    token = await register_owner_for_fixture(client)
    sender = unique_sender()
    order_id = await _confirmed_order_id(client, simulator, database_url, sender, token)
    conversation_id = await _conversation_id_for_order(database_url, order_id)

    created = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/conversations/{conversation_id}/responses",
        headers=auth(token),
    )
    response_id = created.json()["id"]

    # Sending a DRAFT is invalid (the approval is required).
    send_draft = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/responses/{response_id}/send",
        json={"to": sender, "platform": "whatsapp"},
        headers=auth(token),
    )
    assert send_draft.status_code == 400
    assert send_draft.json()["error"]["code"] == "invalid_transition"

    # Explicit approval.
    approved = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/responses/{response_id}/approve",
        headers=auth(token),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    # The production send: UNKNOWN_META → a controlled failure (503), NEVER
    # a fake success; the response stays APPROVED (retryable).
    sent = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/responses/{response_id}/send",
        json={"to": sender, "platform": "whatsapp"},
        headers=auth(token),
    )
    assert sent.status_code == 503
    assert sent.json()["error"]["code"] == "platform_send_unavailable"
    # The response stays APPROVED (retryable) — never a fake "sent".
    after_send = await client.get(
        f"/tenants/{FIXTURE_TENANT_ID}/responses/{response_id}", headers=auth(token)
    )
    assert after_send.json()["status"] == "approved"

    # The audit trail records the workflow.
    # The response audit is separate; verify via the database.
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            audit = (
                await conn.execute(
                    text(
                        "SELECT event FROM response_events "
                        "WHERE response_id = :rid ORDER BY created_at"
                    ),
                    {"rid": uuid.UUID(response_id)},
                )
            ).fetchall()
    finally:
        await engine.dispose()
    audit_events = [r[0] for r in audit]
    assert "created" in audit_events
    assert "approved" in audit_events
    assert "send_failed" in audit_events


async def test_send_with_test_double_succeeds_and_is_audited(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """With a deterministic test double injected (the simulator/test
    boundary), an APPROVED response is sent + audited; duplicate sends are
    rejected (SENT is terminal)."""
    token = await register_owner_for_fixture(client)
    sender = unique_sender()
    order_id = await _confirmed_order_id(client, simulator, database_url, sender, token)
    conversation_id = await _conversation_id_for_order(database_url, order_id)

    created = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/conversations/{conversation_id}/responses",
        headers=auth(token),
    )
    response_id = created.json()["id"]

    approved = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/responses/{response_id}/approve",
        headers=auth(token),
    )
    assert approved.status_code == 200

    # The send via the service with a deterministic test double.
    from app.response_service import send_response as service_send

    engine = create_async_engine(database_url)
    sends: list[tuple[str, str, str]] = []

    class TestSender:
        def send_message(self, platform: str, to: str, content: str):
            sends.append((platform, to, content))
            return None

    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as db:
            # Fetch the response via the ORM.
            from app.models import ResponseDraft

            draft = await db.get(ResponseDraft, uuid.UUID(response_id))
            assert draft is not None
            sent = await service_send(
                db,
                draft,
                actor_user_id=uuid.UUID(user_id_for_token(token, database_url)),
                platform="whatsapp",
                to=sender,
                sender=TestSender(),
            )
            assert sent.status == "sent"
    finally:
        await engine.dispose()

    # The adapter was invoked with the response content (never fabricated).
    assert len(sends) == 1
    assert sends[0][0] == "whatsapp"
    assert sends[0][1] == sender
    assert "2x shirt" in sends[0][2]


def user_id_for_token(token: str, database_url: str) -> str:
    """Resolve the user id for a session token (test helper)."""

    from app.security import hash_token

    token_hash = hash_token(token)
    import psycopg

    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT user_id FROM auth_sessions WHERE token_hash = %s",
            (token_hash,),
        )
        row = cur.fetchone()
    conn.close()
    assert row is not None
    return str(row[0])


# --- Idempotency: concurrent approval + repeated execution ----------------------


async def test_concurrent_approval_is_idempotent(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """Concurrent approvals: one wins, the other gets a controlled error; the
    response is approved exactly once."""
    token = await register_owner_for_fixture(client)
    sender = unique_sender()
    order_id = await _confirmed_order_id(client, simulator, database_url, sender, token)
    conversation_id = await _conversation_id_for_order(database_url, order_id)

    created = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/conversations/{conversation_id}/responses",
        headers=auth(token),
    )
    response_id = created.json()["id"]

    responses = await asyncio.gather(
        *[
            client.post(
                f"/tenants/{FIXTURE_TENANT_ID}/responses/{response_id}/approve",
                headers=auth(token),
            )
            for _ in range(3)
        ],
        return_exceptions=True,
    )
    statuses = [r.status_code for r in responses if hasattr(r, "status_code")]
    # Exactly one 200 (the winner); the rest are controlled errors.
    assert statuses.count(200) == 1, f"expected exactly one approval: {statuses}"

    # The response is approved (one state).
    final = await client.get(
        f"/tenants/{FIXTURE_TENANT_ID}/responses/{response_id}", headers=auth(token)
    )
    assert final.json()["status"] == "approved"


# --- The opt-in control -----------------------------------------------------------


async def test_responses_disabled_tenant_cannot_send(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """The tenant-level opt-in control: responses cannot be created/sent
    while disabled (controlled 403)."""
    token = await register_owner_for_fixture(client)
    sender = unique_sender()
    order_id = await _confirmed_order_id(client, simulator, database_url, sender, token)
    conversation_id = await _conversation_id_for_order(database_url, order_id)

    # Disable responses for the fixture tenant (the opt-in control).
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE tenants SET responses_enabled = false WHERE id = :t"),
                {"t": FIXTURE_TENANT_ID},
            )
    finally:
        await engine.dispose()

    response = await client.post(
        f"/tenants/{FIXTURE_TENANT_ID}/conversations/{conversation_id}/responses",
        headers=auth(token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "responses_disabled"

    # Re-enable for other tests.
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE tenants SET responses_enabled = true WHERE id = :t"),
                {"t": FIXTURE_TENANT_ID},
            )
    finally:
        await engine.dispose()


# --- Response content is never logged -------------------------------------------


async def test_response_content_is_never_logged(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    from structlog.testing import capture_logs

    token = await register_owner_for_fixture(client)
    sender = unique_sender()
    order_id = await _confirmed_order_id(client, simulator, database_url, sender, token)
    conversation_id = await _conversation_id_for_order(database_url, order_id)

    with capture_logs() as logs:
        response = await client.post(
            f"/tenants/{FIXTURE_TENANT_ID}/conversations/{conversation_id}/responses",
            headers=auth(token),
        )
    assert response.status_code == 200
    content = response.json()["content"]
    # The customer-facing content must not appear in any log record.
    assert content not in repr(logs)
