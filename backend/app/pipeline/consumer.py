"""Deterministic pipeline consumer (Phase 6).

Transaction boundary — for each event, ONE transaction covers:

    normalize → resolve/create customer → resolve/create conversation →
    persist message → mark the event processed

Either all of it succeeds consistently, or the transaction rolls back and
the event remains safely retryable (PENDING_PROCESSING/FAILED with the
failure recorded). The event is never marked processed before its
downstream records are durable.

Idempotency (Layer 2 — downstream processing):

- customer resolution: UNIQUE (tenant, platform, external_user_id) with
  SAVEPOINT-based create-or-reuse — concurrent deliveries cannot create
  duplicate customers;
- conversation resolution: partial unique index over OPEN conversations per
  (tenant, customer, connection) with the same create-or-reuse pattern;
- message persistence: UNIQUE ``source_event_id`` — repeated/concurrent
  processing of the same event cannot create duplicate messages.

Retry policy (documented, bounded — no loops):

- The processor processes PENDING_PROCESSING events (optionally FAILED ones
  with ``retry_failed=True``), each in its own transaction.
- A failure increments ``processing_attempts`` and records
  ``last_processing_error``; the event becomes FAILED (inspectable).
- Events are retried at most ``MAX_PROCESSING_ATTEMPTS`` (5) times; beyond
  the cap the processor skips them (no busy-spin, no infinite loop).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    ConversationStatus,
    Customer,
    CustomerPlatformIdentity,
    Message,
    ProcessingState,
    WebhookEvent,
)
from app.pipeline.normalization import NormalizedMessage, normalize_event

logger = structlog.get_logger("pipeline")

# Documented bounded retry policy: an event is retried at most this many
# times (processing_attempts counts every failed attempt).
MAX_PROCESSING_ATTEMPTS = 5


@dataclass
class ProcessingResult:
    processed: int = 0
    already_processed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


async def resolve_or_create_customer(
    db: AsyncSession, tenant_id: uuid.UUID, platform: str, external_user_id: str
) -> Customer:
    """Resolve the customer for a platform identity — deterministically.

    Fast path: an existing identity mapping returns its customer. Otherwise
    the customer + identity are created inside a SAVEPOINT: a concurrent
    racing insert violates the UNIQUE (tenant, platform, external_user_id)
    constraint, rolls back only the savepoint, and the existing identity
    (created by the racing transaction) is returned — one customer per
    identity, enforced at the database level.
    """
    result = await db.execute(
        select(CustomerPlatformIdentity).where(
            CustomerPlatformIdentity.tenant_id == tenant_id,
            CustomerPlatformIdentity.platform == platform,
            CustomerPlatformIdentity.external_user_id == external_user_id,
        )
    )
    existing = result.scalars().first()
    if existing is not None:
        customer = await db.get(Customer, existing.customer_id)
        assert customer is not None
        return customer

    try:
        async with db.begin_nested():
            customer = Customer(tenant_id=tenant_id)
            db.add(customer)
            await db.flush()
            identity = CustomerPlatformIdentity(
                customer_id=customer.id,
                tenant_id=tenant_id,
                platform=platform,
                external_user_id=external_user_id,
            )
            db.add(identity)
            await db.flush()
    except IntegrityError:
        # Concurrent creation raced us; the savepoint rolled back and the
        # outer transaction stays alive. Re-read the winner.
        result = await db.execute(
            select(CustomerPlatformIdentity).where(
                CustomerPlatformIdentity.tenant_id == tenant_id,
                CustomerPlatformIdentity.platform == platform,
                CustomerPlatformIdentity.external_user_id == external_user_id,
            )
        )
        existing = result.scalars().first()
        if existing is None:  # pragma: no cover - defensive
            raise
        customer = await db.get(Customer, existing.customer_id)
        assert customer is not None
        return customer
    logger.info(
        "pipeline.customer_created",
        tenant_id=str(tenant_id),
        customer_id=str(customer.id),
    )
    return customer


async def resolve_or_create_conversation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> Conversation:
    """Resolve the OPEN conversation for (tenant, customer, connection).

    Deterministic: never based on message text or similarity. The partial
    unique index (status='open') backstops concurrent resolution via the
    same SAVEPOINT pattern.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.customer_id == customer_id,
            Conversation.connection_id == connection_id,
            Conversation.status == ConversationStatus.OPEN,
        )
    )
    existing = result.scalars().first()
    if existing is not None:
        return existing

    try:
        async with db.begin_nested():
            conversation = Conversation(
                tenant_id=tenant_id,
                customer_id=customer_id,
                connection_id=connection_id,
            )
            db.add(conversation)
            await db.flush()
    except IntegrityError:
        result = await db.execute(
            select(Conversation).where(
                Conversation.tenant_id == tenant_id,
                Conversation.customer_id == customer_id,
                Conversation.connection_id == connection_id,
                Conversation.status == ConversationStatus.OPEN,
            )
        )
        existing = result.scalars().first()
        if existing is None:  # pragma: no cover - defensive
            raise
        return existing
    logger.info(
        "pipeline.conversation_created",
        tenant_id=str(tenant_id),
        conversation_id=str(conversation.id),
    )
    return conversation


async def process_event(db: AsyncSession, event: WebhookEvent) -> bool:
    """Process ONE pending event; returns True if this call created the
    message.

    One transaction (the caller's session): normalize → customer →
    conversation → message → event processed. All-or-rollback: the event is
    never marked processed before its downstream records are durable.
    """
    if event.processing_state == ProcessingState.PROCESSED:
        # Layer-2 idempotency: already processed — no duplicates, no work.
        logger.info("pipeline.already_processed", event_id=str(event.id))
        return False

    try:
        normalized: NormalizedMessage = normalize_event(event)

        customer = await resolve_or_create_customer(
            db,
            event.tenant_id,
            normalized.platform,
            normalized.external_user_id,
        )
        conversation = await resolve_or_create_conversation(
            db, event.tenant_id, customer.id, event.connection_id
        )

        # Message identity: UNIQUE source_event_id backstops concurrent
        # processing — the same event can never create two messages.
        try:
            async with db.begin_nested():
                message = Message(
                    tenant_id=event.tenant_id,
                    conversation_id=conversation.id,
                    customer_id=customer.id,
                    source_event_id=event.id,
                    external_event_id=normalized.external_event_id,
                    message_type=normalized.message_type,
                    body=normalized.body,
                    external_timestamp=normalized.external_timestamp,
                )
                db.add(message)
                await db.flush()
        except IntegrityError:
            # A racing transaction already persisted this message.
            logger.info("pipeline.message_already_exists", event_id=str(event.id))
            message = None

        # Mark the source event processed IN THE SAME transaction — never
        # before the downstream records are durable.
        event.processing_state = ProcessingState.PROCESSED
        event.processed_at = datetime.now(UTC)
        db.add(event)
        await db.commit()

        logger.info(
            "pipeline.event_processed",
            event_id=str(event.id),
            tenant_id=str(event.tenant_id),
            message_id=str(message.id) if message is not None else None,
        )
        return message is not None
    except Exception:
        # Roll back the whole transaction; the event remains safely
        # retryable. The caller records the failure (separate transaction).
        await db.rollback()
        raise


async def process_pending_events(
    db: AsyncSession,
    *,
    limit: int = 100,
    retry_failed: bool = False,
) -> ProcessingResult:
    """Process pending events (bounded, deterministic — no loops).

    ``retry_failed``: also retry FAILED events (bounded by
    MAX_PROCESSING_ATTEMPTS; events at/over the cap are skipped).
    """
    result = ProcessingResult()

    states = [ProcessingState.PENDING_PROCESSING]
    if retry_failed:
        states.append(ProcessingState.FAILED)

    events_result = await db.execute(
        select(WebhookEvent)
        .where(WebhookEvent.processing_state.in_(states))
        .order_by(WebhookEvent.received_at)
        .limit(limit)
    )
    events = list(events_result.scalars().all())

    for event in events:
        # Captured before processing: after a rollback the ORM object's
        # attributes are expired (reading them would trigger sync IO).
        event_id = event.id
        if event.processing_attempts >= MAX_PROCESSING_ATTEMPTS:
            result.skipped += 1
            logger.warning(
                "pipeline.attempts_exhausted",
                event_id=str(event_id),
                attempts=event.processing_attempts,
            )
            continue
        try:
            created = await process_event(db, event)
            if created:
                result.processed += 1
            else:
                result.already_processed += 1
        except Exception as exc:
            # The transaction rolled back and the event object is expired;
            # re-fetch it fresh (the SELECT refreshes the identity-map
            # object) and record the failure in a separate small transaction.
            # The event stays inspectable and retryable.
            result_events = await db.execute(
                select(WebhookEvent).where(WebhookEvent.id == event_id)
            )
            fresh = result_events.scalars().first()
            if fresh is None:  # pragma: no cover - defensive
                result.failed += 1
                result.errors.append(f"{event_id}: {type(exc).__name__}")
                continue
            fresh.processing_attempts = (fresh.processing_attempts or 0) + 1
            fresh.last_processing_error = str(exc)[:500]
            fresh.processing_state = ProcessingState.FAILED
            db.add(fresh)
            await db.commit()
            result.failed += 1
            result.errors.append(f"{event_id}: {type(exc).__name__}")
            logger.warning(
                "pipeline.event_failed",
                event_id=str(event_id),
                error_type=type(exc).__name__,
            )
    return result
