"""Order extraction service (Phase 7).

Provides functionality to extract order candidates from messages and
persist them for seller review.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.extraction import ExtractionStatus, OrderCandidate, extract_order_candidate_from_text, validate_and_determine_status
from app.models import Message, OrderExtractionCandidate


async def extract_and_save_candidate(
    db: AsyncSession, message: Message
) -> Optional[OrderExtractionCandidate]:
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
        select(OrderExtractionCandidate).where(
            OrderExtractionCandidate.message_id == message.id
        )
    )
    existing = result.scalars().first()
    if existing is not None:
        return existing

    # Extract from the message body.
    if message.body is None:
        # No text to extract from.
        return None

    # Get the AI output (deterministic test double).
    ai_output = extract_order_candidate_from_text(message.body)

    # Validate and determine status.
    candidate, status = validate_and_determine_status(ai_output)

    # Persist the extraction candidate.
    extraction_candidate = OrderExtractionCandidate(
        tenant_id=message.tenant_id,
        conversation_id=message.conversation_id,
        message_id=message.id,
        extracted_data=ai_output,  # store the raw AI output
        status=status.value,  # store the status as string
    )
    db.add(extraction_candidate)
    await db.commit()
    await db.refresh(extraction_candidate)
    return extraction_candidate