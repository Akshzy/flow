"""Conversation, customer and response APIs (Phase 10).

Tenant-scoped, role-aware; all authorization is server-side.
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
    Conversation,
    Customer,
    CustomerPlatformIdentity,
    Message,
    Order,
    ResponseDraft,
    TenantMember,
)
from app.response_service import (
    approve_response,
    classify_intent,
    generate_response_draft,
    send_response,
    update_response_content,
)

logger = structlog.get_logger("responses")

router = APIRouter(tags=["conversations", "customers", "responses"])

OwnerMember = Annotated[TenantMember, Depends(require_membership)]


class ResponseEditIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ResponseSendIn(BaseModel):
    to: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=50)


def _response_out(response: ResponseDraft) -> dict:
    return {
        "id": str(response.id),
        "conversation_id": str(response.conversation_id),
        "order_id": str(response.order_id) if response.order_id else None,
        "intent": response.intent,
        "origin": response.origin,
        "status": response.status,
        "content": response.content,
        "send_attempts": response.send_attempts,
        "last_send_error": response.last_send_error,
        "sent_at": response.sent_at.isoformat() if response.sent_at else None,
    }


def _require_owner(membership: TenantMember) -> TenantMember:
    from app.models import Role

    if membership.role != Role.OWNER:
        raise AppError(
            "You do not have permission to perform this action.",
            code="forbidden",
            status_code=403,
        )
    return membership


# --- Conversations ------------------------------------------------------------


@router.get("/tenants/{tenant_id}/conversations")
async def list_conversations(
    tenant_id: uuid.UUID,
    membership: OwnerMember,
    db: SessionDep,
) -> list[dict]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id)
        .order_by(Conversation.updated_at.desc())
        .limit(100)
    )
    conversations = list(result.scalars().all())
    summaries = []
    for conversation in conversations:
        message_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        latest = message_result.scalars().first()
        summaries.append(
            {
                "id": str(conversation.id),
                "customer_id": str(conversation.customer_id),
                "status": conversation.status,
                "latest_message": latest.body if latest else None,
                "latest_message_at": (latest.created_at.isoformat() if latest else None),
            }
        )
    return summaries


async def _conversation(
    db: AsyncSession, tenant_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
        )
    )
    conversation = result.scalars().first()
    if conversation is None:
        raise AppError("Conversation not found.", code="not_found", status_code=404)
    return conversation


@router.get("/tenants/{tenant_id}/conversations/{conversation_id}")
async def get_conversation(
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    membership: OwnerMember,
    db: SessionDep,
) -> dict:
    conversation = await _conversation(db, tenant_id, conversation_id)
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    messages = list(messages_result.scalars().all())
    order_result = await db.execute(select(Order).where(Order.conversation_id == conversation.id))
    order = order_result.scalars().first()
    intent = await classify_intent(db, conversation.id)
    return {
        "id": str(conversation.id),
        "customer_id": str(conversation.customer_id),
        "status": conversation.status,
        "intent": intent.value,
        "order_id": str(order.id) if order else None,
        "order_status": order.status if order else None,
        "messages": [
            {
                "id": str(m.id),
                "external_event_id": m.external_event_id,
                "message_type": m.message_type,
                "body": m.body,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


# --- Responses ----------------------------------------------------------------


@router.post("/tenants/{tenant_id}/conversations/{conversation_id}/responses")
async def create_response(
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    membership: OwnerMember,
    db: SessionDep,
) -> dict:
    _require_owner(membership)
    conversation = await _conversation(db, tenant_id, conversation_id)
    response = await generate_response_draft(
        db,
        conversation.id,
        created_by_user_id=membership.user_id,
    )
    await db.commit()
    return _response_out(response)


async def _get_response(
    db: AsyncSession, tenant_id: uuid.UUID, response_id: uuid.UUID
) -> ResponseDraft:
    result = await db.execute(
        select(ResponseDraft).where(
            ResponseDraft.id == response_id,
            ResponseDraft.tenant_id == tenant_id,
        )
    )
    response = result.scalars().first()
    if response is None:
        raise AppError("Response not found.", code="not_found", status_code=404)
    return response


@router.get("/tenants/{tenant_id}/responses/{response_id}")
async def get_response(
    tenant_id: uuid.UUID,
    response_id: uuid.UUID,
    membership: OwnerMember,
    db: SessionDep,
) -> dict:
    response = await _get_response(db, tenant_id, response_id)
    return _response_out(response)


@router.patch("/tenants/{tenant_id}/responses/{response_id}")
async def edit_response(
    tenant_id: uuid.UUID,
    response_id: uuid.UUID,
    payload: ResponseEditIn,
    membership: OwnerMember,
    db: SessionDep,
) -> dict:
    _require_owner(membership)
    response = await _get_response(db, tenant_id, response_id)
    try:
        response = await update_response_content(
            db, response, payload.content, actor_user_id=membership.user_id
        )
    except ValueError as exc:
        raise AppError(str(exc), code="invalid_transition", status_code=400) from None
    return _response_out(response)


@router.post("/tenants/{tenant_id}/responses/{response_id}/approve")
async def approve(
    tenant_id: uuid.UUID,
    response_id: uuid.UUID,
    membership: OwnerMember,
    db: SessionDep,
) -> dict:
    _require_owner(membership)
    response = await _get_response(db, tenant_id, response_id)
    try:
        response = await approve_response(db, response, actor_user_id=membership.user_id)
    except ValueError as exc:
        raise AppError(str(exc), code="invalid_transition", status_code=400) from None
    return _response_out(response)


@router.post("/tenants/{tenant_id}/responses/{response_id}/send")
async def send(
    tenant_id: uuid.UUID,
    response_id: uuid.UUID,
    payload: ResponseSendIn,
    membership: OwnerMember,
    db: SessionDep,
) -> dict:
    _require_owner(membership)
    response = await _get_response(db, tenant_id, response_id)
    try:
        # The platform adapter boundary: no injected sender in production —
        # the production send is UNKNOWN_META and refused (never a fake
        # success).
        response = await send_response(
            db,
            response,
            actor_user_id=membership.user_id,
            platform=payload.platform,
            to=payload.to,
            sender=None,
        )
    except ValueError as exc:
        raise AppError(str(exc), code="invalid_transition", status_code=400) from None
    return _response_out(response)


# --- Customers ----------------------------------------------------------------


@router.get("/tenants/{tenant_id}/customers")
async def list_customers(
    tenant_id: uuid.UUID,
    membership: OwnerMember,
    db: SessionDep,
) -> list[dict]:
    result = await db.execute(
        select(Customer)
        .where(Customer.tenant_id == tenant_id)
        .order_by(Customer.created_at)
        .limit(200)
    )
    customers = list(result.scalars().all())
    out = []
    for customer in customers:
        identities_result = await db.execute(
            select(CustomerPlatformIdentity).where(
                CustomerPlatformIdentity.customer_id == customer.id
            )
        )
        identities = list(identities_result.scalars().all())
        orders_result = await db.execute(select(Order).where(Order.customer_id == customer.id))
        orders = list(orders_result.scalars().all())
        out.append(
            {
                "id": str(customer.id),
                "identities": [
                    {
                        "platform": identity.platform,
                        "external_user_id": identity.external_user_id,
                    }
                    for identity in identities
                ],
                "order_count": len(orders),
                "last_order_at": (
                    max(o.created_at for o in orders).isoformat() if orders else None
                ),
            }
        )
    return out
