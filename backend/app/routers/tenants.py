"""Tenant endpoints: creation, listing, retrieval, rename, deletion.

Authorization is enforced server-side on every route:

- ``POST /tenants`` requires authentication; the creator becomes OWNER.
- ``GET /tenants`` returns only tenants the authenticated user is a member
  of (tenant-scoped query — never the full table).
- ``GET /tenants/{id}`` requires membership (404 missing, 403 non-member).
- ``PATCH /tenants/{id}`` and ``DELETE /tenants/{id}`` require the OWNER
  role (403 for plain members and non-members).
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep, require_membership
from app.models import Role, Tenant, TenantMember
from app.schemas import TenantCreate, TenantResponse, TenantUpdate

logger = structlog.get_logger("tenants")

router = APIRouter(prefix="/tenants", tags=["tenants"])


async def _require_owner(tenant_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> TenantMember:
    """Membership dependency requiring the OWNER role."""
    return await require_membership(tenant_id, role=Role.OWNER, user=user, db=db)


# Annotated dependency aliases (no Depends call in argument defaults).
MemberTenant = Annotated[TenantMember, Depends(require_membership)]
OwnerTenant = Annotated[TenantMember, Depends(_require_owner)]


@router.post("", status_code=201, response_model=TenantResponse)
async def create_tenant(payload: TenantCreate, user: CurrentUser, db: SessionDep) -> TenantResponse:
    # Generate the id explicitly: SQLAlchemy applies Python-side defaults at
    # flush time, but the membership needs the id immediately.
    tenant = Tenant(id=uuid.uuid4(), name=payload.name)
    membership = TenantMember(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)
    db.add_all([tenant, membership])
    await db.commit()
    await db.refresh(tenant)
    logger.info("tenant.created", tenant_id=str(tenant.id), user_id=str(user.id))
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
        created_at=tenant.created_at,
        role=Role.OWNER,
    )


@router.get("", response_model=list[TenantResponse])
async def list_tenants(user: CurrentUser, db: SessionDep) -> list[TenantResponse]:
    # Tenant-scoped query: joins memberships and filters by the authenticated
    # user, so only the caller's tenants can ever be returned.
    result = await db.execute(
        select(Tenant, TenantMember.role)
        .join(TenantMember, TenantMember.tenant_id == Tenant.id)
        .where(TenantMember.user_id == user.id)
        .order_by(Tenant.created_at)
    )
    return [
        TenantResponse(
            id=tenant.id,
            name=tenant.name,
            status=tenant.status,
            created_at=tenant.created_at,
            role=role,
        )
        for tenant, role in result.all()
    ]


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    membership: MemberTenant,
    db: SessionDep,
) -> TenantResponse:
    # require_membership already verified the tenant exists and the caller
    # is a member; the identity map serves the tenant without a second query.
    tenant = await db.get(Tenant, tenant_id)
    assert tenant is not None
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
        created_at=tenant.created_at,
        role=membership.role,
    )


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def rename_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    membership: OwnerTenant,
    db: SessionDep,
) -> TenantResponse:
    tenant = await db.get(Tenant, tenant_id)
    assert tenant is not None
    tenant.name = payload.name
    await db.commit()
    await db.refresh(tenant)
    logger.info("tenant.renamed", tenant_id=str(tenant.id), user_id=str(membership.user_id))
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
        created_at=tenant.created_at,
        role=membership.role,
    )


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: uuid.UUID,
    membership: OwnerTenant,
    db: SessionDep,
) -> Response:
    tenant = await db.get(Tenant, tenant_id)
    assert tenant is not None
    # Database-level ON DELETE CASCADE removes the tenant's memberships.
    await db.delete(tenant)
    await db.commit()
    logger.info("tenant.deleted", tenant_id=str(tenant.id), user_id=str(membership.user_id))
    return Response(status_code=204)
