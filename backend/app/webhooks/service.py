"""Webhook gateway service: connection/tenant resolution, idempotency,
event persistence and lifecycle.

Responsibilities (WEBHOOK_SPEC.md flow steps 4-6 + event lifecycle):

- resolve the connection via server-controlled connection mappings
  (VERIFIED_META identifiers: phone_number_id / waba_id) — the tenant is
  derived from the resolved connection, NEVER from client-supplied payload
  fields;
- enforce idempotency at the database level (unique ``dedup_key``), with the
  application-level check as the fast path and the unique constraint as the
  concurrency backstop;
- persist the raw event before acknowledgement: ``RECEIVED`` →
  ``PENDING_PROCESSING`` in a single transaction — a failed write is never
  acknowledged as successful ingestion;
- record processing failures (``FAILED``) for later inspection.

No message normalization, customer management, AI or order logic belongs
here (Phase 6+).
"""

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import (
    ConnectionStatus,
    Platform,
    PlatformConnection,
    ProcessingState,
    WebhookEvent,
)
from app.webhooks.payload import SimulatorEventPayload, dedup_key_for

logger = structlog.get_logger("webhooks")


async def resolve_connection(
    db: AsyncSession, payload: SimulatorEventPayload
) -> PlatformConnection:
    """Resolve the WhatsApp connection via server-controlled mappings.

    Only a CONNECTED connection receives events (an ``initiated`` connection
    has not been authorized yet). A payload's tenant_id field is never
    consulted — the tenant is derived from the resolved connection.
    """
    phone_number_id = payload.phone_number_id
    waba_id = payload.waba_id

    statement = select(PlatformConnection).where(
        PlatformConnection.platform == Platform.WHATSAPP,
        PlatformConnection.status == ConnectionStatus.CONNECTED,
    )
    if phone_number_id:
        statement = statement.where(PlatformConnection.phone_number_id == phone_number_id)
        if waba_id:
            statement = statement.where(PlatformConnection.waba_id == waba_id)
    else:
        # phone_number_id is required by the payload contract; this branch is
        # defensive only.
        statement = statement.where(PlatformConnection.waba_id == waba_id)

    result = await db.execute(statement.order_by(PlatformConnection.created_at.desc()))
    connection = result.scalars().first()
    if connection is None:
        raise AppError(
            "No connected WhatsApp connection matches this event.",
            code="unknown_connection",
            status_code=404,
        )
    return connection


async def persist_event(
    db: AsyncSession,
    connection: PlatformConnection,
    payload: SimulatorEventPayload,
    raw_payload: dict,
) -> tuple[WebhookEvent, bool]:
    """Persist an accepted event; returns (event, created).

    - The event is persisted with the lifecycle transition RECEIVED →
      PENDING_PROCESSING in one transaction, before the HTTP acknowledgement.
    - Idempotency: the application-level dedup check is the fast path; the
      unique ``dedup_key`` constraint is the concurrency backstop (a racing
      duplicate insert raises IntegrityError → mapped to a duplicate result,
      never a second event).
    - The tenant comes from the resolved connection — never from the payload.
    """
    key = dedup_key_for(connection.platform, str(connection.id), payload.message_id)

    # Fast path: an existing record means a duplicate delivery.
    result = await db.execute(select(WebhookEvent).where(WebhookEvent.dedup_key == key))
    existing = result.scalars().first()
    if existing is not None:
        return existing, False

    event = WebhookEvent(
        external_event_id=payload.message_id,
        dedup_key=key,
        platform=connection.platform,
        connection_id=connection.id,
        tenant_id=connection.tenant_id,
        event_type=payload.type,
        raw_payload=raw_payload,
        external_timestamp=payload.timestamp,
        processing_state=ProcessingState.RECEIVED,
    )
    # Lifecycle: RECEIVED → PENDING_PROCESSING in the same transaction.
    event.processing_state = ProcessingState.PENDING_PROCESSING
    db.add(event)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrency backstop: a racing duplicate insert. The existing
        # event stays authoritative; no second event is created.
        await db.rollback()
        result = await db.execute(select(WebhookEvent).where(WebhookEvent.dedup_key == key))
        existing = result.scalars().first()
        if existing is None:  # pragma: no cover - defensive
            raise
        return existing, False
    logger.info(
        "webhook.event_accepted",
        event_id=str(event.id),
        tenant_id=str(event.tenant_id),
        event_type=event.event_type,
    )
    return event, True


async def record_processing_failure(db: AsyncSession, event: WebhookEvent, error: str) -> None:
    """Record a processing failure (event remains inspectable).

    Phase 6 (worker/processor) will use this when a processing attempt
    fails; the event stays durably available for retry.
    """
    event.processing_state = ProcessingState.FAILED
    event.processing_attempts = (event.processing_attempts or 0) + 1
    event.last_processing_error = error
    db.add(event)
    await db.commit()
    logger.warning(
        "webhook.processing_failed",
        event_id=str(event.id),
        tenant_id=str(event.tenant_id),
    )


async def pending_events(db: AsyncSession, limit: int = 100) -> list[WebhookEvent]:
    """Return durably persisted events awaiting processing (Phase 6 entry).

    Accepted events remain available after an application restart; this
    query is how Phase 06 will consume them.
    """
    result = await db.execute(
        select(WebhookEvent)
        .where(WebhookEvent.processing_state == ProcessingState.PENDING_PROCESSING)
        .order_by(WebhookEvent.received_at)
        .limit(limit)
    )
    return list(result.scalars().all())
