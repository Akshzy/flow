"""Order management service (Phase 8).

The authoritative order lifecycle:

    NEW → (NEEDS_REVIEW) → CONFIRMED → PROCESSING → COMPLETED
    CANCELLED / FAILED — terminal

- **Deterministic conversion** (``create_order_from_candidate``): a verified
  extraction candidate becomes an Order + items with NO silent data loss and
  NO invented values (the extraction contract has no price fields — none are
  created). An EXTRACTED (valid) candidate → NEW; an uncertain
  (NEEDS_REVIEW) candidate → NEEDS_REVIEW (the review requirement is
  retained); an INVALID candidate → NO order (nothing valid to review).
  Idempotent at the database level: UNIQUE ``extraction_candidate_id`` (one
  order per candidate) with a SAVEPOINT create-or-reuse — repeated or
  concurrent conversion cannot create duplicate orders. Transactional: the
  candidate, order and items are created in the caller's transaction —
  a failure rolls everything back (no orphans, no falsely completed
  extraction state).

- **Status transitions** (``transition_order``): enforced by the explicit
  state machine below — invalid transitions raise a controlled error and
  never silently succeed (e.g. COMPLETED → PROCESSING). Every transition
  appends an audit event with the acting user.

- **Item edits** (``replace_order_items``): the seller's explicit
  correction — recorded in the audit trail. Quantities never silently
  change; products never silently disappear.

The AI is NOT authoritative: Phase 8 never calls an AI provider, never
silently corrects AI output, never auto-confirms.
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ExtractionStatus,
    Order,
    OrderEvent,
    OrderExtractionCandidate,
    OrderItem,
    OrderStatus,
)

logger = structlog.get_logger("orders")

# The explicit state machine (DATA_MODEL.md). Terminal states allow no
# transitions; COMPLETED → PROCESSING can never silently succeed.
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {
        OrderStatus.NEEDS_REVIEW,
        OrderStatus.CONFIRMED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.NEEDS_REVIEW: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.FAILED: set(),
}


def _record_event(
    db: AsyncSession,
    *,
    order: Order,
    event: str,
    actor_user_id: uuid.UUID | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    detail: str | None = None,
) -> None:
    """Append an audit event (same transaction as the change it records)."""
    db.add(
        OrderEvent(
            order_id=order.id,
            tenant_id=order.tenant_id,
            event=event,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            detail=detail,
        )
    )


async def create_order_from_candidate(
    db: AsyncSession,
    candidate: OrderExtractionCandidate,
    *,
    actor_user_id: uuid.UUID | None = None,
) -> Order | None:
    """Deterministically convert a verified extraction candidate into an
    Order; returns None for INVALID candidates (nothing valid to review).

    - EXTRACTED (valid) candidate → Order NEW.
    - NEEDS_REVIEW (uncertain) candidate → Order NEEDS_REVIEW (the review
      requirement is retained; it can never be auto-confirmed).
    - Idempotent: UNIQUE ``extraction_candidate_id`` with a SAVEPOINT
      create-or-reuse — repeated or concurrent conversion returns the
      existing order (one order per candidate).
    - No silent data loss: the candidate's extracted items are persisted as
      order items verbatim (product/quantity/variant/size/color); no price
      fields exist in the extraction contract and none are invented.
    - Transactional: everything is created in the caller's transaction; a
      failure rolls the candidate, order and items back together.
    """
    # Fast path: the order already exists (repeated conversion).
    result = await db.execute(select(Order).where(Order.extraction_candidate_id == candidate.id))
    existing = result.scalars().first()
    if existing is not None:
        return existing

    if candidate.status == ExtractionStatus.INVALID.value:
        # An invalid candidate has no valid data to review — no order is
        # created (deterministic; recorded via the extraction status).
        return None

    if candidate.status == ExtractionStatus.NEEDS_REVIEW.value:
        initial_status = OrderStatus.NEEDS_REVIEW
    else:
        initial_status = OrderStatus.NEW

    try:
        async with db.begin_nested():
            order = Order(
                tenant_id=candidate.tenant_id,
                customer_id=await _candidate_customer_id(db, candidate),
                extraction_candidate_id=candidate.id,
                conversation_id=candidate.conversation_id,
                status=initial_status,
            )
            db.add(order)
            await db.flush()

            extracted_items = (candidate.extracted_data or {}).get("items") or []
            persisted_items = 0
            for item in extracted_items:
                # No invention: only the fields the extraction provided.
                # INCOMPLETE items (a NEEDS_REVIEW candidate's items may lack
                # the quantity or product) are NOT persisted as order items —
                # the OrderItem schema requires product + quantity and none
                # is invented. They remain review-visible in the candidate's
                # extracted_data; the seller's explicit correction (audited)
                # completes them.
                product = item.get("product")
                quantity = item.get("quantity")
                if (
                    not isinstance(product, str)
                    or not product.strip()
                    or not isinstance(quantity, int)
                    or quantity <= 0
                ):
                    continue
                db.add(
                    OrderItem(
                        order_id=order.id,
                        tenant_id=order.tenant_id,
                        product=product,
                        quantity=quantity,
                        variant=item.get("variant"),
                        size=item.get("size"),
                        color=item.get("color"),
                    )
                )
                persisted_items += 1
            await db.flush()

            _record_event(
                db,
                order=order,
                event="created",
                actor_user_id=actor_user_id,
                to_status=initial_status.value,
                detail="Created from extraction candidate",
            )
    except IntegrityError:
        # Concurrent conversion raced us; the savepoint rolled back and the
        # existing order (created by the racing transaction) is returned.
        result = await db.execute(
            select(Order).where(Order.extraction_candidate_id == candidate.id)
        )
        existing = result.scalars().first()
        if existing is None:  # pragma: no cover - defensive
            raise
        return existing

    logger.info(
        "order.created",
        order_id=str(order.id),
        tenant_id=str(order.tenant_id),
        status=order.status,
    )
    return order


async def _candidate_customer_id(
    db: AsyncSession, candidate: OrderExtractionCandidate
) -> uuid.UUID:
    """The candidate's customer id via the proven ownership chain
    (candidate → message → customer, from the Phase 6 customer model).

    The customer association is never fabricated: an extraction candidate
    without a customer reference cannot become an order.
    """
    from app.models import Message

    message = await db.get(Message, candidate.message_id)
    if message is None or message.customer_id is None:
        raise ValueError(
            "The extraction candidate has no customer reference; the order "
            "cannot be created without fabricating identity."
        )
    return message.customer_id


async def transition_order(
    db: AsyncSession,
    order: Order,
    to_status: OrderStatus,
    *,
    actor_user_id: uuid.UUID | None = None,
) -> Order:
    """Apply a status transition — enforced by the explicit state machine.

    Invalid transitions (including any transition out of a terminal state,
    e.g. COMPLETED → PROCESSING) raise a controlled error and never silently
    succeed. Every applied transition appends an audit event.
    """
    from_status = OrderStatus(order.status)
    allowed = VALID_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise ValueError(f"Invalid order transition: {from_status.value} -> {to_status.value}")

    order.status = to_status
    db.add(order)
    _record_event(
        db,
        order=order,
        event="status_changed",
        actor_user_id=actor_user_id,
        from_status=from_status.value,
        to_status=to_status.value,
    )
    await db.commit()
    logger.info(
        "order.status_changed",
        order_id=str(order.id),
        from_status=from_status.value,
        to_status=to_status.value,
    )
    return order


async def replace_order_items(
    db: AsyncSession,
    order: Order,
    items: list[dict],
    *,
    actor_user_id: uuid.UUID | None = None,
) -> Order:
    """The seller's explicit item correction (recorded in the audit trail).

    No invention: every item must provide product and quantity; optional
    fields (variant/size/color) may be provided or omitted. The replacement
    is the seller's explicit decision — quantities never silently change and
    products never silently disappear (the change is audited).
    """
    # Validate all items BEFORE mutating (no partial replacement on failure).
    validated: list[dict] = []
    for item in items:
        product = item.get("product")
        quantity = item.get("quantity")
        if not isinstance(product, str) or not product.strip():
            raise ValueError("Each item requires a product.")
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Each item requires a positive quantity.")
        validated.append(
            {
                "product": product,
                "quantity": quantity,
                "variant": item.get("variant"),
                "size": item.get("size"),
                "color": item.get("color"),
            }
        )

    # Replace the items (the seller's explicit correction).
    existing_items = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    for existing in existing_items.scalars().all():
        await db.delete(existing)
    for item in validated:
        db.add(
            OrderItem(
                order_id=order.id,
                tenant_id=order.tenant_id,
                product=item["product"],
                quantity=item["quantity"],
                variant=item["variant"],
                size=item["size"],
                color=item["color"],
            )
        )
    _record_event(
        db,
        order=order,
        event="items_edited",
        actor_user_id=actor_user_id,
        detail=f"{len(validated)} item(s) corrected by the seller",
    )
    await db.commit()
    logger.info("order.items_edited", order_id=str(order.id))
    return order
