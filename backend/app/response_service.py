"""Controlled seller response service (Phase 10).

The response lifecycle:

    DRAFT → APPROVED → SENT; FAILED (a send failure — bounded retry)

- **Intent classification** (``classify_intent``): deterministic — derived
  from existing state (the conversation's confirmed order), never from an
  LLM, never from fuzzy matching. A conversation with a CONFIRMED order →
  ``order_confirmation``; otherwise ``unsupported`` (no response is
  generated for unsupported intents — the seller is not given a response
  template that the state cannot back).

- **Response generation** (``generate_response_draft``): a deterministic
  template built ONLY from the confirmed order's actual data — the origin is
  ``ai_suggested`` (AI may suggest content; AI does NOT gain authority to
  send). Missing information is never invented.

- **Approval** (``approve_response``): EXPLICIT seller action — the only
  path to send. No automatic AI → SEND transition exists anywhere.

- **Send** (``send_response``): only APPROVED responses, only while the
  tenant's opt-in control is enabled, via the platform adapter boundary
  (the production Meta send is UNKNOWN_META and blocked — the adapter
  refuses to guess; the failure is recorded and the response stays
  APPROVED/retryable, never a fake success). Bounded: send_attempts with
  MAX_SEND_ATTEMPTS.

- **Audit**: every transition appends a ``response_events`` audit record
  (the same transaction as the change); the response content is never
  logged.
"""

import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import (
    Conversation,
    Order,
    OrderStatus,
    ResponseDraft,
    ResponseEvent,
    ResponseIntent,
    ResponseOrigin,
    ResponseStatus,
    Tenant,
)

logger = structlog.get_logger("responses")

# Documented bounded retry policy for send attempts (no loops).
MAX_SEND_ATTEMPTS = 5


class MessageSender(Protocol):
    """The platform adapter boundary for sending (Phase 10).

    The PRODUCTION sender is the Meta adapter's send operation — UNKNOWN_META
    (the exact Meta send API has not been verified from official
    documentation in this environment) and therefore BLOCKED: the production
    adapter raises a controlled error and no fake success is ever reported.
    A deterministic test double may be injected for local testing.
    """

    def send_message(
        self, connection_platform: str, to: str, content: str
    ) -> Awaitable[None] | None:
        """Send a message via the platform. Must never log the content."""
        ...


VALID_TRANSITIONS: dict[ResponseStatus, set[ResponseStatus]] = {
    ResponseStatus.DRAFT: {ResponseStatus.APPROVED},
    ResponseStatus.APPROVED: {ResponseStatus.SENT, ResponseStatus.FAILED},
    ResponseStatus.SENT: set(),  # terminal
    ResponseStatus.FAILED: {ResponseStatus.SENT},  # bounded retry via send
}


@dataclass(frozen=True)
class ResponseContext:
    """What the seller needs to inspect before approving (WHO/WHAT/WHY)."""

    conversation_id: str
    customer_id: str
    platform: str
    order: dict[str, Any] | None
    intent: str


def _record_event(
    db: AsyncSession,
    *,
    response: ResponseDraft,
    event: str,
    actor_user_id: uuid.UUID | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    detail: str | None = None,
) -> None:
    """Append an audit event (same transaction as the change)."""
    db.add(
        ResponseEvent(
            response_id=response.id,
            tenant_id=response.tenant_id,
            event=event,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            detail=detail,
        )
    )


async def classify_intent(db: AsyncSession, conversation_id: uuid.UUID) -> ResponseIntent:
    """Deterministic intent classification for a conversation.

    Derived from existing state only: a conversation with a CONFIRMED order
    → order_confirmation; otherwise unsupported. No LLM; no fuzzy matching.
    """
    result = await db.execute(
        select(Order).where(
            Order.conversation_id == conversation_id,
            Order.status == OrderStatus.CONFIRMED,
        )
    )
    confirmed = result.scalars().first()
    if confirmed is not None:
        return ResponseIntent.ORDER_CONFIRMATION
    return ResponseIntent.UNSUPPORTED


def generate_response_content(intent: ResponseIntent, order: Order | None) -> str:
    """Deterministic response content built ONLY from the confirmed order's
    actual data (never invented; never a price — prices do not exist in the
    extraction contract)."""
    if intent != ResponseIntent.ORDER_CONFIRMATION or order is None:
        raise AppError(
            "No response can be generated for this conversation: no "
            "confirmed order exists to base a response on.",
            code="no_response_available",
            status_code=422,
        )
    # The items come from the order's actual data (the caller fetches them);
    # the content template is deterministic.
    return "ORDER_CONFIRMATION_TEMPLATE"


async def generate_response_draft(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    created_by_user_id: uuid.UUID,
) -> ResponseDraft:
    """Create a response draft (origin: ai_suggested).

    Deterministic: the intent is classified from existing state and the
    content is a template built from the confirmed order's actual items.
    Missing information is never invented; unsupported intents raise a
    controlled error (the seller is not offered a response the state cannot
    back).
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id is None:
        raise AppError("Conversation not found.", code="not_found", status_code=404)

    # The tenant-level opt-in control.
    tenant = await db.get(Tenant, conversation.tenant_id)
    if tenant is None or not tenant.responses_enabled:
        raise AppError(
            "Responses are not enabled for this business.",
            code="responses_disabled",
            status_code=403,
        )

    intent = await classify_intent(db, conversation_id)
    if intent != ResponseIntent.ORDER_CONFIRMATION:
        raise AppError(
            "No response can be generated for this conversation: no "
            "confirmed order exists to base a response on.",
            code="no_response_available",
            status_code=422,
        )

    order_result = await db.execute(
        select(Order).where(
            Order.conversation_id == conversation_id,
            Order.status == OrderStatus.CONFIRMED,
        )
    )
    order = order_result.scalars().first()
    assert order is not None

    # The items (the order's actual data — never invented).
    from app.models import OrderItem

    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    items = list(items_result.scalars().all())
    item_parts = [f"{item.quantity}x {item.product}" for item in items]
    content = (
        f"Hi! Your order has been received: {', '.join(item_parts)}. "
        "We will update you when it ships."
    )

    response = ResponseDraft(
        tenant_id=conversation.tenant_id,
        conversation_id=conversation_id,
        order_id=order.id,
        intent=intent,
        content=content,
        origin=ResponseOrigin.AI_SUGGESTED,
        status=ResponseStatus.DRAFT,
        created_by_user_id=created_by_user_id,
    )
    db.add(response)
    try:
        await db.flush()
    except IntegrityError:  # pragma: no cover - defensive
        raise
    _record_event(
        db,
        response=response,
        event="created",
        actor_user_id=created_by_user_id,
        to_status=ResponseStatus.DRAFT.value,
        detail="AI suggested (deterministic, from the confirmed order)",
    )
    logger.info(
        "response.created",
        response_id=str(response.id),
        tenant_id=str(response.tenant_id),
        intent=intent.value,
    )
    return response


async def approve_response(
    db: AsyncSession, response: ResponseDraft, *, actor_user_id: uuid.UUID
) -> ResponseDraft:
    """EXPLICIT seller approval — the only path to send."""
    from_status = ResponseStatus(response.status)
    if ResponseStatus.APPROVED not in VALID_TRANSITIONS.get(from_status, set()):
        raise ValueError(f"Invalid response transition: {from_status.value} -> approved")
    response.status = ResponseStatus.APPROVED
    db.add(response)
    _record_event(
        db,
        response=response,
        event="approved",
        actor_user_id=actor_user_id,
        from_status=from_status.value,
        to_status=ResponseStatus.APPROVED.value,
        detail="Seller approved",
    )
    await db.commit()
    logger.info(
        "response.approved",
        response_id=str(response.id),
        actor_user_id=str(actor_user_id),
    )
    return response


async def send_response(
    db: AsyncSession,
    response: ResponseDraft,
    *,
    actor_user_id: uuid.UUID,
    platform: str,
    to: str,
    sender: MessageSender | None = None,
) -> ResponseDraft:
    """Send an APPROVED response via the platform adapter boundary.

    - Only APPROVED responses can be sent (no automatic transitions).
    - The tenant's opt-in control must be enabled.
    - The PRODUCTION adapter (UNKNOWN_META) is not implemented: with no
      injected sender the send fails with a controlled error — the response
      stays APPROVED (retryable); a fake success is never reported.
    - Bounded: send_attempts with MAX_SEND_ATTEMPTS; beyond the cap the
      send is refused (no busy-spin).
    - The response content is never logged.
    """
    from_status = ResponseStatus(response.status)
    if ResponseStatus.SENT not in VALID_TRANSITIONS.get(from_status, set()):
        raise ValueError(f"Invalid response transition: {from_status.value} -> sent")
    if response.send_attempts >= MAX_SEND_ATTEMPTS:
        raise AppError(
            "Maximum send attempts reached.",
            code="send_attempts_exhausted",
            status_code=409,
        )

    # The tenant's opt-in control.
    tenant = await db.get(Tenant, response.tenant_id)
    if tenant is None or not tenant.responses_enabled:
        raise AppError(
            "Responses are not enabled for this business.",
            code="responses_disabled",
            status_code=403,
        )

    response.send_attempts = (response.send_attempts or 0) + 1
    try:
        if sender is None:
            # The production adapter boundary: the Meta send API is
            # UNKNOWN_META and not implemented — refuse (no fake success).
            raise AppError(
                "Sending via the platform is not configured yet.",
                code="platform_send_unavailable",
                status_code=503,
            )
        result = sender.send_message(platform, to, response.content)
        if result is not None:
            await result
    except Exception as exc:
        # The failure is recorded; the response stays APPROVED (retryable).
        response.last_send_error = str(exc)[:500]
        db.add(response)
        _record_event(
            db,
            response=response,
            event="send_failed",
            actor_user_id=actor_user_id,
            from_status=from_status.value,
            to_status=None,  # the response stays APPROVED (retryable)
            detail="Send failed via the platform adapter",
        )
        await db.commit()
        logger.warning(
            "response.send_failed",
            response_id=str(response.id),
            error_type=type(exc).__name__,
        )
        raise
    response.status = ResponseStatus.SENT
    response.sent_at = datetime.now(UTC)
    response.last_send_error = None
    db.add(response)
    _record_event(
        db,
        response=response,
        event="sent",
        actor_user_id=actor_user_id,
        from_status=from_status.value,
        to_status=ResponseStatus.SENT.value,
    )
    await db.commit()
    logger.info(
        "response.sent",
        response_id=str(response.id),
        actor_user_id=str(actor_user_id),
    )
    return response


async def update_response_content(
    db: AsyncSession,
    response: ResponseDraft,
    content: str,
    *,
    actor_user_id: uuid.UUID,
) -> ResponseDraft:
    """The seller's edit of the response content (only DRAFT responses)."""
    from_status = ResponseStatus(response.status)
    if from_status != ResponseStatus.DRAFT:
        raise ValueError(f"Only draft responses can be edited (current: {from_status.value})")
    if not content.strip():
        raise ValueError("The response content cannot be empty.")
    response.content = content
    response.origin = ResponseOrigin.SELLER_WRITTEN
    db.add(response)
    _record_event(
        db,
        response=response,
        event="edited",
        actor_user_id=actor_user_id,
        detail="Seller edited the response",
    )
    await db.commit()
    logger.info("response.edited", response_id=str(response.id))
    return response
