"""Webhook gateway API tests (Phase 5) — via the deterministic simulator.

The simulator submits events over HTTP through the ASGI stack — the ACTUAL
HTTP boundary. It never bypasses the gateway or writes into the event
database.

REAL META API TEST = BLOCKED (no credentials); SIMULATOR_ONLY contract.
"""

import asyncio
import uuid

import httpx
import pytest

from simulator.client import SimulatorClient
from simulator.fixtures import (
    CONNECTION_PHONE_NUMBER_ID,
    MESSAGE_ID_VALID_1,
    build_event,
)
from simulator.setup import create_fixture_connection
from tests.helpers import create_tenant, register_and_login

TEST_SECRET = "simulator-test-secret"


@pytest.fixture()
async def simulator(client: httpx.AsyncClient, database_url: str) -> SimulatorClient:
    """Simulator client bound to the real app (ASGI HTTP boundary), with the
    TEST-ONLY connected fixture connection in place."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from simulator.setup import create_fixture_connection

    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
    finally:
        await engine.dispose()
    return SimulatorClient(base_url="http://testserver", secret=TEST_SECRET)


def unique_message_id() -> str:
    """A unique message id per test (the stable fixtures are for the
    simulator determinism tests and the CLI, not for cross-test reuse —
    duplicate deliveries must not collide across tests)."""
    return f"wamid.sim-{uuid.uuid4().hex[:12]}"


async def ensure_fixture_connection(database_url: str) -> None:
    """Async wrapper: create the TEST-ONLY fixture connection (the sync
    setup entry uses asyncio.run, which cannot run inside the test's event
    loop)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
    finally:
        await engine.dispose()


@pytest.fixture()
async def production_client(app_settings):
    """An app running in production mode (simulator auth disabled)."""
    import httpx

    from app.config import Settings
    from app.main import create_app

    production_settings = Settings(
        database_url=app_settings.database_url,
        environment="production",
        log_level="WARNING",
    )
    application = create_app(settings=production_settings)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c, SimulatorClient(base_url="http://t", secret=TEST_SECRET)


# --- Authentication -----------------------------------------------------------


async def test_valid_authentication_accepts_event(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    response = await simulator.submit(build_event(unique_message_id()), client=client)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["event_id"]
    assert body["processing_state"] == "pending_processing"


async def test_missing_authentication_rejected(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    response = await simulator.submit(
        build_event(MESSAGE_ID_VALID_1), client=client, omit_signature=True
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_invalid_authentication_rejected(client: httpx.AsyncClient, database_url: str):
    await ensure_fixture_connection(database_url)
    wrong = SimulatorClient(base_url="http://testserver", secret="wrong-secret")
    response = await wrong.submit(build_event(MESSAGE_ID_VALID_1), client=client)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_modified_signed_payload_rejected(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """A payload modified after signing must be rejected (raw-byte auth)."""
    original = build_event(unique_message_id())
    from simulator.fixtures import serialize, signature_for

    original_raw = serialize(original)
    tampered = dict(original)
    tampered["text"] = {"body": "tampered after signing"}

    # The tampered body is presented with the ORIGINAL signature: raw-byte
    # authentication must reject it.
    response = await simulator.submit(
        tampered, client=client, override_signature=signature_for(TEST_SECRET, original_raw)
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_disabled_simulator_mode_in_production(production_client, database_url: str):
    """In production, simulator auth is disabled and the endpoint is blocked."""
    production_http, prod_simulator = production_client
    await ensure_fixture_connection(database_url)
    response = await prod_simulator.submit(build_event(MESSAGE_ID_VALID_1), client=production_http)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "webhook_not_configured"


# --- Validation ----------------------------------------------------------------


async def test_valid_payload_accepted(client: httpx.AsyncClient, simulator: SimulatorClient):
    response = await simulator.submit(build_event(unique_message_id()), client=client)
    assert response.status_code == 202


async def test_malformed_json_rejected(client: httpx.AsyncClient, simulator: SimulatorClient):
    from simulator.fixtures import signature_for

    malformed = b"{not-json"
    _, headers = simulator.build_request({})
    headers["X-Floww-Simulator-Signature"] = signature_for(TEST_SECRET, malformed)
    response = await client.post("/webhooks/whatsapp", content=malformed, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_missing_required_fields_rejected(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    response = await simulator.submit(
        {"type": "messages", "phone_number_id": CONNECTION_PHONE_NUMBER_ID},
        client=client,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_unsupported_event_type_rejected(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    response = await simulator.submit(
        {
            "type": "unsupported",
            "phone_number_id": CONNECTION_PHONE_NUMBER_ID,
            "from": "15550000001",
            "message_id": "wamid.sim-0200",
        },
        client=client,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_oversized_request_rejected(client: httpx.AsyncClient, simulator: SimulatorClient):
    response = await simulator.submit(
        build_event("wamid.sim-0201", text="x" * 2_000_000), client=client
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


# --- Idempotency ----------------------------------------------------------------


async def test_sequential_duplicate_creates_one_event(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    message_id = unique_message_id()
    payload = build_event(message_id)
    first = await simulator.submit(payload, client=client)
    assert first.status_code == 202
    second = await simulator.submit(payload, client=client)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    # Same underlying event, deterministic response.
    assert second.json()["event_id"] == first.json()["event_id"]


async def test_repeated_duplicates_never_create_more_events(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    message_id = unique_message_id()
    payload = build_event(message_id)
    await simulator.submit(payload, client=client)
    for _ in range(4):
        response = await simulator.submit(payload, client=client)
        assert response.status_code == 200

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

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


async def test_concurrent_duplicates_create_one_event(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """Concurrent duplicate submissions: the DB unique constraint is the
    backstop — exactly one event survives."""
    message_id = unique_message_id()
    payload = build_event(message_id)
    responses = await asyncio.gather(
        *[simulator.submit(payload, client=client) for _ in range(6)],
        return_exceptions=True,
    )
    statuses = [r.status_code for r in responses if hasattr(r, "status_code")]
    assert len(statuses) == 6, "some submissions failed at the network level"
    assert statuses.count(202) == 1, f"expected exactly one 202: {statuses}"
    assert statuses.count(200) == 5, f"expected 5 duplicates: {statuses}"

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

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


async def test_distinct_valid_events_both_persisted(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """Different senders / message ids are distinct events (all accepted)."""
    first = await simulator.submit(
        build_event("wamid.sim-0300", sender="15550000001"), client=client
    )
    second = await simulator.submit(
        build_event("wamid.sim-0301", sender="15550000001"), client=client
    )
    third = await simulator.submit(
        build_event("wamid.sim-0302", sender="15550000002"), client=client
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert third.status_code == 202

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            count = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM webhook_events "
                        "WHERE external_event_id IN ('wamid.sim-0300', "
                        "'wamid.sim-0301', 'wamid.sim-0302')"
                    )
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert count == 3


async def test_tenant_scoped_uniqueness(client: httpx.AsyncClient, database_url: str):
    """The same external event ID under a DIFFERENT connection (tenant) is a
    DISTINCT event — the dedup scope is platform:connection:external_id."""
    from cryptography.fernet import Fernet
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.credential_store import CredentialStore
    from app.meta import MetaConnectionService

    await ensure_fixture_connection(database_url)  # tenant A's connected connection

    # Tenant B: an owner + a second connected connection with a DIFFERENT
    # phone_number_id, but the SAME external event id.
    token_b, user_b = await register_and_login(client)
    tenant_b = await create_tenant(client, token_b, "Tenant B Dedup Scope")

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with factory() as session:
            service = MetaConnectionService(CredentialStore(Fernet.generate_key().decode()))
            connection = service.initiate(uuid.UUID(tenant_b["id"]), uuid.UUID(user_b["id"]))
            service.connect(
                connection,
                waba_id="888888888",
                phone_number_id="777777777",  # different from the fixture
            )
            session.add(connection)
            await session.commit()
    finally:
        await engine.dispose()

    # The SAME external event id under two different connections (tenants):
    # the dedup scope is platform:connection:external_id, so both are
    # accepted as distinct events.
    message_id = unique_message_id()
    simulator_a = SimulatorClient(base_url="http://testserver", secret=TEST_SECRET)
    first = await simulator_a.submit(
        build_event(message_id),
        client=client,  # fixture connection (tenant A)
    )
    assert first.status_code == 202
    simulator_b = SimulatorClient(base_url="http://testserver", secret=TEST_SECRET)
    response = await simulator_b.submit(
        build_event(
            message_id,
            phone_number_id="777777777",
            waba_id="888888888",
        ),
        client=client,
    )
    assert response.status_code == 202  # distinct event, accepted

    from sqlalchemy import text

    engine2 = create_async_engine(database_url)
    try:
        async with engine2.connect() as conn:
            count = (
                await conn.execute(
                    text("SELECT count(*) FROM webhook_events WHERE external_event_id = :eid"),
                    {"eid": message_id},
                )
            ).scalar_one()
    finally:
        await engine2.dispose()
    assert count == 2  # one per connection (tenant)


# --- Isolation ----------------------------------------------------------------


async def test_unknown_connection_rejected(client: httpx.AsyncClient, simulator: SimulatorClient):
    from simulator.fixtures import UNMAPPED_PHONE_NUMBER_ID

    response = await simulator.submit(
        build_event("wamid.sim-0400", phone_number_id=UNMAPPED_PHONE_NUMBER_ID, waba_id=None),
        client=client,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_connection"


async def test_forged_connection_identifiers_rejected(
    client: httpx.AsyncClient, simulator: SimulatorClient
):
    """Forged identifiers that match no connected connection are rejected."""
    response = await simulator.submit(
        build_event("wamid.sim-0401", phone_number_id="123123123", waba_id="456456456"),
        client=client,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_connection"


async def test_forged_tenant_in_payload_is_ignored(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """A tenant_id inside the payload is NEVER trusted: the tenant resolves
    via the connection mapping, so a forged tenant_id cannot redirect the
    event to another tenant."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    forged = build_event("wamid.sim-0402")
    forged["tenant_id"] = "00000000-0000-0000-0000-0000000000ff"  # forged

    response = await simulator.submit(forged, client=client)
    assert response.status_code == 202  # accepted (resolved via connection)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT t.id FROM webhook_events e "
                        "JOIN tenants t ON t.id = e.tenant_id "
                        "WHERE e.external_event_id = :eid"
                    ),
                    {"eid": "wamid.sim-0402"},
                )
            ).first()
    finally:
        await engine.dispose()
    assert row is not None
    # The event's tenant is the fixture connection's tenant — NOT the forged id.
    assert str(row[0]) == "00000000-0000-0000-0000-00000000a001"


# --- Persistence ----------------------------------------------------------------


async def test_accepted_event_persisted_with_raw_payload(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    message_id = unique_message_id()
    payload = build_event(message_id, text="order message content 99")
    response = await simulator.submit(payload, client=client)
    assert response.status_code == 202
    event_id = response.json()["event_id"]

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT processing_state, raw_payload, external_event_id, "
                        "platform, event_type FROM webhook_events WHERE id = :eid"
                    ),
                    {"eid": event_id},
                )
            ).first()
    finally:
        await engine.dispose()

    assert row is not None
    assert row[0] == "pending_processing"  # persisted before the ack
    assert row[1]["from"] == "15550000001"  # raw payload retained
    assert row[2] == message_id
    assert row[3] == "whatsapp"
    assert row[4] == "messages"


async def test_persistence_failure_no_false_ack(
    client: httpx.AsyncClient, simulator: SimulatorClient, monkeypatch
):
    """Force a persistence failure: the gateway must not acknowledge."""
    import app.webhooks.router as webhook_router

    async def failing_persist(*args, **kwargs):
        raise RuntimeError("forced database failure")

    monkeypatch.setattr(webhook_router, "persist_event", failing_persist)

    # raise_app_exceptions=False mirrors a real server: the 500 envelope the
    # server error middleware sent is returned (the ack is never "accepted").
    import httpx

    application = client._transport.app
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        response = await simulator.submit(build_event(unique_message_id()), client=c)

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    # No false ack: the response is not accepted/duplicate.
    assert body.get("status") not in ("accepted", "duplicate")


async def test_events_survive_application_restart(client: httpx.AsyncClient, database_url: str):
    """An accepted event remains available after an application restart;
    a duplicate after the restart stays a duplicate."""
    import httpx

    from app.main import create_app

    await ensure_fixture_connection(database_url)
    simulator = SimulatorClient(base_url="http://testserver", secret=TEST_SECRET)

    # First app instance: accept the event.
    application = create_app()
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            first = await simulator.submit(build_event("wamid.sim-0500"), client=c)
            assert first.status_code == 202

    # "Restart": a NEW app instance against the same database.
    restarted = create_app()
    async with restarted.router.lifespan_context(restarted):
        transport = httpx.ASGITransport(app=restarted)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            # The event is still durably available.
            import sqlalchemy.ext.asyncio as sa_async

            engine = sa_async.create_async_engine(database_url)
            try:
                from sqlalchemy import text

                async with engine.connect() as conn:
                    state = (
                        await conn.execute(
                            text(
                                "SELECT processing_state FROM webhook_events "
                                "WHERE external_event_id = 'wamid.sim-0500'"
                            )
                        )
                    ).scalar_one()
            finally:
                await engine.dispose()
            assert state == "pending_processing"

            # A duplicate after the restart: deterministic duplicate response.
            duplicate = await simulator.submit(build_event("wamid.sim-0500"), client=c)
            assert duplicate.status_code == 200
            assert duplicate.json()["status"] == "duplicate"
            assert duplicate.json()["event_id"] == first.json()["event_id"]
