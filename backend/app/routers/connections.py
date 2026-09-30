"""WhatsApp connection endpoints (tenant-scoped, Phase 4).

Authorization is enforced server-side on every route:

- ``GET  /tenants/{id}/connection`` — members can view connection status.
- ``POST /tenants/{id}/connection/initiate`` — OWNER starts the connection
  lifecycle (an ``initiated`` record is created; the Meta authorization step
  itself is not implemented yet — the response states this explicitly).
  Idempotent while initiated; 409 when already connected.
- ``DELETE /tenants/{id}/connection`` — OWNER disconnects (history kept,
  credential material destroyed).

A client-supplied tenant ID is never proof of access; the connection is
resolved through the authenticated user's membership. Connection responses
never include credential material or raw Meta payloads.
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.credential_store import CredentialStore
from app.deps import CurrentUser, SessionDep, require_membership
from app.errors import AppError
from app.meta import MetaConnectionService
from app.models import ConnectionStatus, Platform, PlatformConnection, TenantMember
from app.schemas import ConnectionInitiateResponse, ConnectionResponse

logger = structlog.get_logger("connections")

router = APIRouter(tags=["connections"])

# Annotated dependency aliases are defined after the dependency functions
# below (OwnerTenant references _require_owner).
MemberTenant = Annotated[TenantMember, Depends(require_membership)]


async def _require_owner(tenant_id: uuid.UUID, membership: MemberTenant) -> TenantMember:
    """Membership dependency requiring the OWNER role."""
    from app.models import Role

    if membership.role != Role.OWNER:
        raise AppError(
            "You do not have permission to perform this action.",
            code="forbidden",
            status_code=403,
        )
    return membership


# Annotated dependency aliases (no Depends call in argument defaults).
OwnerTenant = Annotated[TenantMember, Depends(_require_owner)]


def _connection_service(settings: Settings) -> MetaConnectionService:
    """Build the Meta connection service with its credential store."""
    store = (
        CredentialStore(settings.credential_encryption_key)
        if settings.credential_encryption_key
        else None
    )
    return MetaConnectionService(store)


async def _active_connection(db: AsyncSession, tenant_id: uuid.UUID) -> PlatformConnection | None:
    """The tenant's active (initiated/connected) WhatsApp connection.

    The partial unique index guarantees at most one active connection per
    (tenant, platform); .first() is used defensively regardless.
    """
    result = await db.execute(
        select(PlatformConnection)
        .where(
            PlatformConnection.tenant_id == tenant_id,
            PlatformConnection.platform == Platform.WHATSAPP,
            PlatformConnection.status.in_([ConnectionStatus.INITIATED, ConnectionStatus.CONNECTED]),
        )
        .order_by(PlatformConnection.created_at.desc())
    )
    return result.scalars().first()


def _connection_response(connection: PlatformConnection) -> ConnectionResponse:
    """Build a connection response (never includes credential material)."""
    return ConnectionResponse(
        id=connection.id,
        platform=connection.platform,
        status=connection.status,
        waba_id=connection.waba_id,
        phone_number_id=connection.phone_number_id,
        connected_at=connection.connected_at,
        disconnected_at=connection.disconnected_at,
    )


@router.get("/tenants/{tenant_id}/connection", response_model=ConnectionResponse)
async def get_connection(
    tenant_id: uuid.UUID, membership: MemberTenant, db: SessionDep
) -> ConnectionResponse:
    connection = await _active_connection(db, tenant_id)
    if connection is None:
        return ConnectionResponse(platform=Platform.WHATSAPP, status=ConnectionStatus.DISCONNECTED)
    return _connection_response(connection)


@router.post(
    "/tenants/{tenant_id}/connection/initiate",
    response_model=ConnectionInitiateResponse,
)
async def initiate_connection(
    tenant_id: uuid.UUID,
    request: Request,
    membership: OwnerTenant,
    user: CurrentUser,
    db: SessionDep,
) -> ConnectionInitiateResponse:
    settings: Settings = request.app.state.settings
    service = _connection_service(settings)

    existing = await _active_connection(db, tenant_id)
    if existing is not None and existing.status == ConnectionStatus.CONNECTED:
        raise AppError(
            "WhatsApp is already connected for this business.",
            code="conflict",
            status_code=409,
        )
    if existing is not None and existing.status == ConnectionStatus.INITIATED:
        # Idempotent re-initiation while the connection is not completed.
        return ConnectionInitiateResponse(
            platform=Platform.WHATSAPP,
            status=ConnectionStatus.INITIATED,
            detail="Meta authorization is pending configuration.",
        )

    connection = service.initiate(tenant_id, user.id)
    db.add(connection)
    await db.commit()
    logger.info(
        "connection.initiated",
        tenant_id=str(tenant_id),
        connection_id=str(connection.id),
        user_id=str(user.id),
    )
    return ConnectionInitiateResponse(
        platform=Platform.WHATSAPP,
        status=ConnectionStatus.INITIATED,
        detail="Meta authorization is pending configuration.",
    )


@router.delete("/tenants/{tenant_id}/connection", response_model=ConnectionResponse)
async def disconnect_connection(
    tenant_id: uuid.UUID,
    request: Request,
    membership: OwnerTenant,
    db: SessionDep,
) -> ConnectionResponse:
    settings: Settings = request.app.state.settings
    service = _connection_service(settings)

    connection = await _active_connection(db, tenant_id)
    if connection is None:
        raise AppError(
            "No active WhatsApp connection to disconnect.",
            code="not_found",
            status_code=404,
        )
    service.disconnect(connection)
    db.add(connection)
    await db.commit()
    return _connection_response(connection)
