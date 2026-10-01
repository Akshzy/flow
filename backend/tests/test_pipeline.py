"""Message pipeline tests (Phase 6) — via the real Phase 05 boundary.

Flow: simulator → HTTP webhook → persisted event → Phase 06 processor →
customer → conversation → message. Deterministic, idempotent, isolated.
"""

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from simulator.client import SimulatorClient
from simulator.fixtures import (
    CONNECTION_PHONE_NUMBER_ID,
    build_event,
)
from simulator.setup import FIXTURE_TENANT_ID, create_fixture_connection

TEST_SECRET = "simulator-test-secret"


def unique_message_id() -> str:
    """A unique message id per test (the stable fixtures are for the
    simulator determinism tests and the CLI, not for cross-test reuse —
    duplicate deliveries must not collide across tests)."""
    return f"wamid.sim-{uuid.uuid4().hex[:12]}"


def unique_sender() -> str:
    """A unique synthetic sender per test (shared fixture senders would
    collide across tests through the shared identity; the processor also
    consumes leftover pending events from other test files, so identity-
    scoped assertions must use per-test identities)."""
    return f"1555{uuid.uuid4().hex[:8]}000"


@pytest.fixture()
async def simulator(client: httpx.AsyncClient, database_url: str) -> SimulatorClient:
    """Simulator client bound to the real app, with the fixture connection."""
    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as session:
            await create_fixture_connection(session)
    finally:
        await engine.dispose()
    return SimulatorClient(base_url="http://testserver", secret=TEST_SECRET)


async def run_processor(database_url: str, *, monkeypatch: None = None, **kwargs):
    """Run the deterministic processor against the database."""
    from app.pipeline.consumer import process_pending_events

    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with factory() as db:
            return await process_pending_events(db, **kwargs)
    finally:
        await engine.dispose()


async def submit_event(simulator: SimulatorClient, client, **event_kwargs) -> dict:
    """Submit an event through the real HTTP gateway; returns the ack body."""
    response = await simulator.submit(build_event(**event_kwargs), client=client)
    assert response.status_code == 202, response.text
    return response.json()


# --- Customer resolution --------------------------------------------------------


async def test_first_message_creates_customer(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    sender = unique_sender()
    await submit_event(
        simulator, client, message_id=f"wamid.p6-{uuid.uuid4().hex[:8]}", sender=sender
    )
    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            # Scoped by the sender: deterministic via the UNIQUE identity
            # constraint (one customer per platform identity).
            customers = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM customers c "
                        "JOIN customer_platform_identities i "
                        "ON i.customer_id = c.id "
                        "WHERE i.external_user_id = :sender"
                    ),
                    {"sender": sender},
                )
            ).scalar_one()
            identities = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM customer_platform_identities "
                        "WHERE external_user_id = :sender"
                    ),
                    {"sender": sender},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert customers == 1
    assert identities == 1


async def test_second_message_reuses_customer(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    sender = unique_sender()
    event_ids = []
    for _ in range(2):
        ack = await submit_event(
            simulator, client, message_id=f"wamid.p6-{uuid.uuid4().hex[:8]}", sender=sender
        )
        event_ids.append(ack["event_id"])
    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            customers = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM customers c "
                        "JOIN customer_platform_identities i "
                        "ON i.customer_id = c.id "
                        "WHERE i.external_user_id = :sender"
                    ),
                    {"sender": sender},
                )
            ).scalar_one()
            messages = (
                await conn.execute(
                    text("SELECT count(*) FROM messages WHERE source_event_id = ANY(:eids)"),
                    {"eids": event_ids},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    # Same sender → ONE customer; this test's two events → TWO messages.
    assert customers == 1
    assert messages == 2


async def test_different_sender_creates_different_customer(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    sender_1 = unique_sender()
    sender_2 = unique_sender()
    await submit_event(
        simulator, client, message_id=f"wamid.p6-{uuid.uuid4().hex[:8]}", sender=sender_1
    )
    await submit_event(
        simulator, client, message_id=f"wamid.p6-{uuid.uuid4().hex[:8]}", sender=sender_2
    )
    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            customers = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM customer_platform_identities "
                        "WHERE external_user_id = ANY(:senders)"
                    ),
                    {"senders": [sender_1, sender_2]},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    # Different identities → TWO distinct customers (deterministic via the
    # UNIQUE identity constraint).
    assert customers == 2


async def test_concurrent_customer_creation_produces_one_customer(
    client: httpx.AsyncClient, database_url: str
):
    """Concurrent deliveries must not create duplicate customers — the
    UNIQUE (tenant, platform, external_user_id) constraint + SAVEPOINT
    create-or-reuse protects this."""
    from app.pipeline.consumer import resolve_or_create_customer

    engine = create_async_engine(database_url)
    try:
        # Two separate sessions racing to resolve the SAME identity.
        async def resolve():
            factory = async_sessionmaker(bind=engine, expire_on_commit=False)
            async with factory() as db:
                customer = await resolve_or_create_customer(
                    db, FIXTURE_TENANT_ID, "whatsapp", "15557770001"
                )
                await db.commit()
                return str(customer.id)

        results = await asyncio.gather(resolve(), resolve())
        assert results[0] == results[1]  # the SAME customer

        async with engine.connect() as conn:
            identities = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM customer_platform_identities "
                        "WHERE external_user_id = '15557770001'"
                    )
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert identities == 1


# --- Conversation resolution ------------------------------------------------------


async def test_first_message_creates_conversation(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    sender = unique_sender()
    await submit_event(
        simulator, client, message_id=f"wamid.p6-{uuid.uuid4().hex[:8]}", sender=sender
    )
    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            # Scoped by the sender: one OPEN conversation per
            # (tenant, customer, connection) — deterministic via the partial
            # unique index.
            conversations = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM conversations c "
                        "JOIN customer_platform_identities i "
                        "ON i.customer_id = c.customer_id "
                        "WHERE i.external_user_id = :sender"
                    ),
                    {"sender": sender},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert conversations == 1


async def test_subsequent_message_reuses_conversation(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    sender = unique_sender()
    event_ids = []
    for _ in range(3):
        ack = await submit_event(
            simulator, client, message_id=f"wamid.p6-{uuid.uuid4().hex[:8]}", sender=sender
        )
        event_ids.append(ack["event_id"])
    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            conversations = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM conversations c "
                        "JOIN customer_platform_identities i "
                        "ON i.customer_id = c.customer_id "
                        "WHERE i.external_user_id = :sender"
                    ),
                    {"sender": sender},
                )
            ).scalar_one()
            messages = (
                await conn.execute(
                    text("SELECT count(*) FROM messages WHERE source_event_id = ANY(:eids)"),
                    {"eids": event_ids},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    # Deterministic resolution: ONE conversation for the sender; this
    # test's three events → THREE messages in it.
    assert conversations == 1
    assert messages == 3


async def test_concurrent_conversation_resolution_does_not_duplicate(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    from app.pipeline.consumer import (
        resolve_or_create_conversation,
        resolve_or_create_customer,
    )

    # The fixture tenant/connection must exist (the simulator fixture
    # creates them idempotently).
    engine = create_async_engine(database_url)
    try:

        async def resolve():
            factory = async_sessionmaker(bind=engine, expire_on_commit=False)
            async with factory() as db:
                customer = await resolve_or_create_customer(
                    db, FIXTURE_TENANT_ID, "whatsapp", "15557770002"
                )
                conversation = await resolve_or_create_conversation(
                    db, FIXTURE_TENANT_ID, customer.id, _fixture_connection_id(engine)
                )
                await db.commit()
                return str(conversation.id)

        results = await asyncio.gather(resolve(), resolve())
        assert results[0] == results[1]

        async with engine.connect() as conn:
            count = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM conversations c "
                        "JOIN customer_platform_identities i "
                        "ON i.customer_id = c.customer_id "
                        "WHERE i.external_user_id = '15557770002'"
                    )
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert count == 1


def _fixture_connection_id(engine) -> uuid.UUID:
    """The fixture connection id (synchronous query on the engine's URL)."""
    import psycopg

    url = engine.url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://"
    )
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM platform_connections WHERE phone_number_id = %s",
            (CONNECTION_PHONE_NUMBER_ID,),
        )
        row = cur.fetchone()
    conn.close()
    assert row is not None
    return row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(row[0])


# --- Message persistence / idempotency ----------------------------------------------


async def test_message_persists_with_trace_chain(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    await submit_event(simulator, client, message_id=message_id, text="trace chain message")
    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT m.tenant_id, c.tenant_id, e.tenant_id, "
                        "m.external_event_id, m.message_type, m.body "
                        "FROM messages m "
                        "JOIN conversations c ON c.id = m.conversation_id "
                        "JOIN webhook_events e ON e.id = m.source_event_id "
                        "WHERE m.external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).first()
    finally:
        await engine.dispose()

    assert row is not None
    # The trace chain is intact and tenant-consistent.
    assert row[0] == row[1] == row[2]  # tenant → conversation → event
    assert row[3] == message_id
    assert row[4] == "text"
    assert row[5] == "trace chain message"


async def test_repeated_processing_does_not_duplicate_message(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """The same event processed 1x, 2x and 5x → one logical message."""
    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    await submit_event(simulator, client, message_id=message_id)

    for _ in range(5):
        await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            messages = (
                await conn.execute(
                    text("SELECT count(*) FROM messages WHERE external_event_id = :eid"),
                    {"eid": message_id},
                )
            ).scalar_one()
            state = (
                await conn.execute(
                    text(
                        "SELECT processing_state FROM webhook_events WHERE external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert messages == 1
    assert state == "processed"


async def test_concurrent_processing_does_not_duplicate_message(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """Concurrent processing of the same event: the UNIQUE source_event_id
    backstop — one message, one processed event."""
    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    await submit_event(simulator, client, message_id=message_id)

    results = await asyncio.gather(*[run_processor(database_url) for _ in range(4)])
    created_total = sum(r.processed for r in results)
    assert created_total == 1, f"exactly one message must be created: {results}"

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            messages = (
                await conn.execute(
                    text("SELECT count(*) FROM messages WHERE external_event_id = :eid"),
                    {"eid": message_id},
                )
            ).scalar_one()
            state = (
                await conn.execute(
                    text(
                        "SELECT processing_state FROM webhook_events WHERE external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert messages == 1
    assert state == "processed"


# --- Event lifecycle -----------------------------------------------------------------


async def test_pending_event_becomes_processed(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    sender = unique_sender()
    ack = await submit_event(
        simulator, client, message_id=f"wamid.p6-{uuid.uuid4().hex[:8]}", sender=sender
    )
    assert ack["processing_state"] == "pending_processing"

    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT processing_state, processed_at FROM webhook_events WHERE id = :eid"
                    ),
                    {"eid": ack["event_id"]},
                )
            ).first()
    finally:
        await engine.dispose()
    assert row is not None
    assert row[0] == "processed"
    assert row[1] is not None


async def test_failed_processing_remains_inspectable_and_retryable(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str, monkeypatch
):
    """A failure is recorded (FAILED + attempts + error); a bounded retry
    succeeds afterwards."""
    from app.pipeline import consumer as pipeline_consumer

    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    await submit_event(simulator, client, message_id=message_id)

    # Force a normalization failure for the first processing attempt.
    def failing_normalize(event):
        raise RuntimeError("forced normalization failure")

    monkeypatch.setattr(pipeline_consumer, "normalize_event", failing_normalize)
    result = await run_processor(database_url)
    monkeypatch.undo()
    assert result.failed == 1

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT processing_state, processing_attempts, "
                        "last_processing_error FROM webhook_events "
                        "WHERE external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).first()
            messages = (
                await conn.execute(
                    text("SELECT count(*) FROM messages WHERE external_event_id = :eid"),
                    {"eid": message_id},
                )
            ).scalar_one()
    finally:
        await engine.dispose()

    # The failure is inspectable; NO partial downstream records exist
    # (transaction rollback) and the event was NOT marked processed.
    assert row[0] == "failed"
    assert row[1] == 1
    assert "forced normalization failure" in row[2]
    assert messages == 0

    # Bounded retry (explicit) succeeds.
    result = await run_processor(database_url, retry_failed=True)
    assert result.processed == 1

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            state = (
                await conn.execute(
                    text(
                        "SELECT processing_state FROM webhook_events WHERE external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).scalar_one()
            messages = (
                await conn.execute(
                    text("SELECT count(*) FROM messages WHERE external_event_id = :eid"),
                    {"eid": message_id},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert state == "processed"
    assert messages == 1


async def test_retry_cap_prevents_endless_retries(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """Events at/over MAX_PROCESSING_ATTEMPTS are skipped (no busy-spin)."""
    from app.pipeline.consumer import MAX_PROCESSING_ATTEMPTS

    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    await submit_event(simulator, client, message_id=message_id)

    # Drive the event to the attempt cap.
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE webhook_events SET processing_attempts = :cap, "
                    "processing_state = 'failed' WHERE external_event_id = :eid"
                ),
                {"cap": MAX_PROCESSING_ATTEMPTS, "eid": message_id},
            )
    finally:
        await engine.dispose()

    result = await run_processor(database_url, retry_failed=True)
    assert result.skipped == 1
    assert result.processed == 0


# --- Tenant isolation ------------------------------------------------------------------


async def test_downstream_records_inherit_event_tenant(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """Tenant A's event → Tenant A customer/conversation/message."""
    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    await submit_event(simulator, client, message_id=message_id)
    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT m.tenant_id, c.tenant_id, cu.tenant_id, e.tenant_id "
                        "FROM messages m "
                        "JOIN conversations c ON c.id = m.conversation_id "
                        "JOIN customers cu ON cu.id = m.customer_id "
                        "JOIN webhook_events e ON e.id = m.source_event_id "
                        "WHERE m.external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).first()
    finally:
        await engine.dispose()

    assert row is not None
    assert row == (FIXTURE_TENANT_ID, FIXTURE_TENANT_ID, FIXTURE_TENANT_ID, FIXTURE_TENANT_ID)


async def test_forged_payload_tenant_does_not_alter_resolution(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """A forged tenant_id in the raw payload must not alter the resolved
    tenant (the gateway ignores it; the pipeline uses the event's tenant)."""
    forged_tenant = "00000000-0000-0000-0000-0000000000ff"
    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    payload = build_event(message_id)
    payload["tenant_id"] = forged_tenant  # forged field in the raw payload

    response = await simulator.submit(payload, client=client)
    assert response.status_code == 202
    await run_processor(database_url)

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT m.tenant_id, e.tenant_id FROM messages m "
                        "JOIN webhook_events e ON e.id = m.source_event_id "
                        "WHERE m.external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).first()
    finally:
        await engine.dispose()

    assert row is not None
    assert row[0] == FIXTURE_TENANT_ID  # NOT the forged tenant
    assert row[1] == FIXTURE_TENANT_ID


# --- Deterministic replay (section 25) ---------------------------------------------------


async def test_deterministic_replay_one_of_everything(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str
):
    """The same event, run 1x/2x/5x/concurrently → ONE customer, ONE
    conversation, ONE message, ONE processed event."""
    sender = unique_sender()
    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    await submit_event(simulator, client, message_id=message_id, sender=sender)

    # 1x, 2x, 5x sequential
    for _ in range(5):
        await run_processor(database_url)
    # concurrent
    await asyncio.gather(*[run_processor(database_url) for _ in range(4)])

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            customers = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM customer_platform_identities "
                        "WHERE external_user_id = :sender"
                    ),
                    {"sender": sender},
                )
            ).scalar_one()
            conversations = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM conversations c "
                        "JOIN customer_platform_identities i "
                        "ON i.customer_id = c.customer_id "
                        "WHERE i.external_user_id = :sender"
                    ),
                    {"sender": sender},
                )
            ).scalar_one()
            messages = (
                await conn.execute(
                    text("SELECT count(*) FROM messages WHERE external_event_id = :eid"),
                    {"eid": message_id},
                )
            ).scalar_one()
            events = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM webhook_events "
                        "WHERE external_event_id = :eid AND processing_state = 'processed'"
                    ),
                    {"eid": message_id},
                )
            ).scalar_one()
    finally:
        await engine.dispose()

    assert customers == 1
    assert conversations == 1
    assert messages == 1
    assert events == 1


# --- Database failure -------------------------------------------------------------------


async def test_database_failure_is_recorded_not_faked(
    client: httpx.AsyncClient, simulator: SimulatorClient, database_url: str, monkeypatch
):
    """A transient DB failure: the transaction rolls back, the failure is
    recorded, and the event remains retryable."""
    from app.pipeline import consumer as pipeline_consumer

    message_id = f"wamid.p6-{uuid.uuid4().hex[:8]}"
    await submit_event(simulator, client, message_id=message_id)

    original = pipeline_consumer.resolve_or_create_customer

    calls = {"count": 0}

    async def flaky(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient database failure")
        return await original(*args, **kwargs)

    monkeypatch.setattr(pipeline_consumer, "resolve_or_create_customer", flaky)
    result = await run_processor(database_url)
    monkeypatch.undo()

    assert result.failed == 1
    assert calls["count"] == 1  # the retry happens in the NEXT processor run

    # Retry (explicit, bounded): the event is FAILED after the recorded
    # failure and processes successfully on retry.
    result = await run_processor(database_url, retry_failed=True)
    assert result.processed == 1

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            state = (
                await conn.execute(
                    text(
                        "SELECT processing_state FROM webhook_events WHERE external_event_id = :eid"
                    ),
                    {"eid": message_id},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert state == "processed"
