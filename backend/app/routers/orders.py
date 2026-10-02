"""Order management API (Phase 8) — tenant-scoped, role-aware seller review.

Authorization is enforced server-side on every route (the authenticated
user's membership; a client-supplied tenant/order ID is never proof of
access):

- ``GET /tenants/{id}/orders``                       — member: list (tenant-scoped)
- ``GET /tenants/{id}/orders/{order_id}``            — member: inspect (with items)
- ``GET /tenants/{id}/orders/{order_id}/events``     — member: audit history
- ``PATCH /tenants/{id}/orders/{order_id}``          — OWNER: correct items
- ``POST /tenants/{id}/orders/{order_id}/confirm``   — OWNER: → CONFIRMED
- ``POST /tenants/{id}/orders/{order_id}/process``   — OWNER: → PROCESSING
- ``POST /tenants/{id}/orders/{order_id}/complete``  — OWNER: → COMPLETED
- ``POST /tenants/{id}/orders/{order_id}/cancel``    — OWNER: → CANCELLED

The seller's confirm action IS the human-review decision (the AI candidate
is never auto-confirmed). Invalid state transitions raise a controlled error
and never silently succeed.
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import SessionDep, require_membership
from app.errors import AppError
from app.models import (
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    TenantMember,
)
from app.order_service import replace_order_items, transition_order

logger = structlog.get_logger("orders")

router = APIRouter(tags=["orders"])


class OrderItemIn(BaseModel):
    product: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0)
    variant: str | None = Field(default=None, max_length=200)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)


class OrderUpdate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    product: str
    quantity: int
    variant: str | None
    size: str | None
    color: str | None


class OrderResponse(BaseModel):
    id: uuid.UUID
    status: str
    customer_id: uuid.UUID
    extraction_candidate_id: uuid.UUID
    items: list[OrderItemResponse]
    created_at: str | None = None
    updated_at: str | None = None


class OrderEventResponse(BaseModel):
    event: str
    from_status: str | None
    to_status: str | None
    actor_user_id: uuid.UUID | None
    detail: str | None
    created_at: str | None = None


async def _get_order(db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    """Tenant-scoped order lookup: the order must belong to the path tenant
    (a forged/foreign order id can never be resolved)."""
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    order = result.scalars().first()
    if order is None:
        raise AppError("Order not found.", code="not_found", status_code=404)
    return order


def _order_response(order: Order, items: list[OrderItem]) -> dict:
    return {
        "id": str(order.id),
        "status": order.status,
        "customer_id": str(order.customer_id),
        "extraction_candidate_id": str(order.extraction_candidate_id),
        "items": [
            {
                "id": str(item.id),
                "product": item.product,
                "quantity": item.quantity,
                "variant": item.variant,
                "size": item.size,
                "color": item.color,
            }
            for item in items
        ],
    }


async def _order_items(db: AsyncSession, order_id: uuid.UUID) -> list[OrderItem]:
    result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    return list(result.scalars().all())


@router.get("/tenants/{tenant_id}/orders")
async def list_orders(
    tenant_id: uuid.UUID,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
) -> list[dict]:
    # Tenant-scoped query: only the path tenant's orders can ever be returned.
    result = await db.execute(
        select(Order).where(Order.tenant_id == tenant_id).order_by(Order.created_at)
    )
    orders = list(result.scalars().all())
    responses = []
    for order in orders:
        items = await _order_items(db, order.id)
        responses.append(_order_response(order, items))
    return responses


@router.get("/tenants/{tenant_id}/orders/{order_id}")
async def get_order(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
) -> dict:
    order = await _get_order(db, tenant_id, order_id)
    items = await _order_items(db, order.id)
    return _order_response(order, items)


@router.get("/tenants/{tenant_id}/orders/{order_id}/events")
async def get_order_events(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
) -> list[dict]:
    await _get_order(db, tenant_id, order_id)
    result = await db.execute(
        select(OrderEvent).where(OrderEvent.order_id == order_id).order_by(OrderEvent.created_at)
    )
    return [
        {
            "event": event.event,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
            "detail": event.detail,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in result.scalars().all()
    ]


@router.patch("/tenants/{tenant_id}/orders/{order_id}")
async def update_order(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    payload: OrderUpdate,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
) -> dict:
    from app.models import Role

    if membership.role != Role.OWNER:
        raise AppError(
            "You do not have permission to perform this action.",
            code="forbidden",
            status_code=403,
        )
    order = await _get_order(db, tenant_id, order_id)
    try:
        order = await replace_order_items(
            db,
            order,
            [item.model_dump() for item in payload.items],
            actor_user_id=membership.user_id,
        )
    except ValueError as exc:
        raise AppError(str(exc), code="validation_error", status_code=422) from None
    items = await _order_items(db, order.id)
    return _order_response(order, items)


async def _confirm_transition(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
    to_status: OrderStatus,
) -> dict:
    from app.models import Role

    if membership.role != Role.OWNER:
        raise AppError(
            "You do not have permission to perform this action.",
            code="forbidden",
            status_code=403,
        )
    order = await _get_order(db, tenant_id, order_id)
    try:
        order = await transition_order(db, order, to_status, actor_user_id=membership.user_id)
    except ValueError as exc:
        # Invalid state transitions never silently succeed: a controlled
        # 400 error (the state is unchanged).
        raise AppError(str(exc), code="invalid_transition", status_code=400) from None
    items = await _order_items(db, order.id)
    return _order_response(order, items)


@router.post("/tenants/{tenant_id}/orders/{order_id}/confirm")
async def confirm_order(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
) -> dict:
    return await _confirm_transition(tenant_id, order_id, membership, db, OrderStatus.CONFIRMED)


@router.post("/tenants/{tenant_id}/orders/{order_id}/process")
async def process_order(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
) -> dict:
    return await _confirm_transition(tenant_id, order_id, membership, db, OrderStatus.PROCESSING)


@router.post("/tenants/{tenant_id}/orders/{order_id}/complete")
async def complete_order(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
) -> dict:
    return await _confirm_transition(tenant_id, order_id, membership, db, OrderStatus.COMPLETED)


@router.post("/tenants/{tenant_id}/orders/{order_id}/cancel")
async def cancel_order(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    membership: Annotated[TenantMember, Depends(require_membership)],
    db: SessionDep,
) -> dict:
    return await _confirm_transition(tenant_id, order_id, membership, db, OrderStatus.CANCELLED)
