"""Order extraction service (Phase 7).

Provides functionality to extract order candidates from messages and
persist them for seller review.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.extraction import (
    extract_order_candidate_from_text,
    validate_and_determine_status,
)
from app.models import Message, OrderExtractionCandidate

logger = structlog.get_logger("extraction")


async def extract_and_save_candidate(
    db: AsyncSession, message: Message
) -> OrderExtractionCandidate | None:
    """Extract an order candidate from a message and persist it.

    If an extraction candidate already exists for the message, it is returned
    without re-extraction (idempotency).

    Args:
        db: The database session.
        message: The message to extract from.

    Returns:
        The existing or newly created extraction candidate, or None if the
        message is not of type text.
    """
    # Only process text messages for now.
    if message.message_type != "text":
        return None

    # Check if we already have an extraction candidate for this message.
    result = await db.execute(
        select(OrderExtractionCandidate).where(OrderExtractionCandidate.message_id == message.id)
    )
    existing = result.scalars().first()
    if existing is not None:
        # Idempotent: the candidate exists. A partial failure may have left
        # a candidate without its order — ensure the order exists too (the
        # conversion is idempotent: an existing order is returned as-is).
        # This path owns its transaction: the change is committed here.
        from app.order_service import create_order_from_candidate

        await create_order_from_candidate(db, existing)
        await db.commit()
        return existing

    # Extract from the message body.
    if message.body is None:
        # No text to extract from.
        return None

    # Get the AI output (deterministic test double).
    ai_output = extract_order_candidate_from_text(message.body)

    # Validate and determine status.
    _candidate, status = validate_and_determine_status(ai_output)

    # Persist the extraction candidate; then deterministically convert the
    # verified candidate into an Order (Phase 8) in the same transaction:
    # the candidate, order and items commit together — a failure rolls
    # everything back (no orphans, no falsely completed extraction state).
    # An INVALID candidate becomes no order; a NEEDS_REVIEW candidate
    # becomes an order that retains its review requirement. The seller is
    # NEVER auto-confirmed.
    #
    # SAVEPOINT create-or-reuse: a concurrent processor racing on the same
    # message violates the UNIQUE (message_id) constraint — the savepoint
    # rolls back (the session stays usable) and the racing winner's
    # candidate is returned (with its order ensured).
    from app.order_service import create_order_from_candidate

    extraction_candidate = OrderExtractionCandidate(
        tenant_id=message.tenant_id,
        conversation_id=message.conversation_id,
        message_id=message.id,
        extracted_data=ai_output,  # store the raw AI output
        status=status.value,  # store the status as string
    )
    try:
        async with db.begin_nested():
            db.add(extraction_candidate)
            await db.flush()
            order = await create_order_from_candidate(db, extraction_candidate)
    except IntegrityError:
        # A concurrent processor created the candidate first; re-read the
        # winner and ensure its order exists (idempotent conversion).
        result = await db.execute(
            select(OrderExtractionCandidate).where(
                OrderExtractionCandidate.message_id == message.id
            )
        )
        existing = result.scalars().first()
        if existing is None:  # pragma: no cover - defensive
            raise
        await create_order_from_candidate(db, existing)
        await db.commit()
        return existing

    if order is not None:
        logger.info(
            "order.created_from_candidate",
            order_id=str(order.id),
            candidate_id=str(extraction_candidate.id),
            status=order.status,
        )

    await db.commit()
    await db.refresh(extraction_candidate)
    return extraction_candidate
