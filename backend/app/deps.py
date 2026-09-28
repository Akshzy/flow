"""FastAPI dependencies: authentication and authorization.

Authentication (who is this?):

- ``get_current_user`` validates the ``Authorization: Bearer <token>``
  header against server-side sessions (hash lookup + expiry) and returns
  the authenticated ``User``. Missing/invalid/malformed credentials raise
  401 ``unauthorized``; expired sessions raise 401 ``session_expired``.

Authorization (what is this user allowed to access?):

- ``require_membership`` resolves the tenant from the path and verifies —
  against the ``tenant_members`` table, never against client claims — that
  the authenticated user is a member (optionally with the required role).
  A missing tenant raises 404 ``not_found``; an existing tenant the user
  cannot access raises 403 ``forbidden``.

A tenant ID supplied by the client is never sufficient proof of access.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError
from app.models import AuthSession, Role, Tenant, TenantMember, User
from app.security import hash_token

# auto_error=False: missing credentials are handled here so every failure
# returns the consistent error envelope.
_bearer_scheme = HTTPBearer(auto_error=False, description="Session bearer token")


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide a request-scoped database session."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Validate the bearer token and return the authenticated user."""
    if credentials is None or not credentials.credentials:
        raise AppError("Authentication required.", code="unauthorized", status_code=401)
    auth_session = await _get_valid_session(db, credentials.credentials)
    user = await db.get(User, auth_session.user_id)
    if user is None:
        # Session points at a deleted user; the session is not usable.
        raise AppError("Authentication required.", code="unauthorized", status_code=401)
    return user


async def _get_valid_session(db: AsyncSession, token: str) -> AuthSession:
    token_hash = hash_token(token)
    session = await db.get(AuthSession, token_hash)
    if session is None:
        raise AppError("Authentication required.", code="unauthorized", status_code=401)
    if session.expires_at <= datetime.now(UTC):
        # Expired sessions are distinguishable from unknown tokens. Expired
        # rows are removed by periodic cleanup (later hardening phase).
        raise AppError("Session has expired.", code="session_expired", status_code=401)
    return session


# Type aliases for endpoint signatures (defined after the dependency
# functions; no Depends call in argument defaults).
CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


async def require_membership(
    tenant_id: uuid.UUID,
    user: CurrentUser,
    db: SessionDep,
    role: Role | None = None,
) -> TenantMember:
    """Verify the authenticated user's access to the path tenant.

    ``role`` optionally requires a specific membership role (e.g. OWNER for
    destructive tenant operations).
    """
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise AppError("Tenant not found.", code="not_found", status_code=404)

    result = await db.execute(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant_id,
            TenantMember.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise AppError(
            "You do not have access to this tenant.",
            code="forbidden",
            status_code=403,
        )
    if role is not None and membership.role != role:
        raise AppError(
            "You do not have permission to perform this action.",
            code="forbidden",
            status_code=403,
        )
    return membership
