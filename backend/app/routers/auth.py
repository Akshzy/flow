"""Authentication endpoints: registration, login, session validation, logout.

- Passwords are verified against argon2id hashes and never stored or logged.
- Login returns an opaque bearer token; only its SHA-256 hash is persisted.
- Unknown email and wrong password return the identical generic 401 so the
  endpoint cannot be used to enumerate accounts.
- Logout invalidates the presented session server-side (the token becomes
  unusable immediately).
"""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Request
from sqlalchemy import select

from app.config import Settings
from app.deps import Credentials, CurrentUser, SessionDep
from app.errors import AppError
from app.models import AuthSession, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.security import generate_token, hash_password, hash_token, verify_password

logger = structlog.get_logger("auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserResponse)
async def register(payload: RegisterRequest, db: SessionDep) -> User:
    email = payload.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise AppError(
            "An account with this email already exists.",
            code="conflict",
            status_code=409,
        )
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("auth.registered", user_id=str(user.id))
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: SessionDep) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, payload.password):
        # Identical generic error for unknown email and wrong password: the
        # endpoint must not reveal whether an account exists (enumeration).
        logger.warning("auth.login_failed")
        raise AppError("Invalid email or password.", code="invalid_credentials", status_code=401)

    settings: Settings = request.app.state.settings
    token = generate_token()
    now = datetime.now(UTC)
    auth_session = AuthSession(
        token_hash=hash_token(token),
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(auth_session)
    await db.commit()
    logger.info("auth.login", user_id=str(user.id))
    return TokenResponse(
        token=token,
        token_type="bearer",
        expires_at=auth_session.expires_at,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> User:
    return user


@router.post("/logout")
async def logout(credentials: Credentials, user: CurrentUser, db: SessionDep) -> dict:
    assert credentials is not None  # guaranteed by get_current_user
    auth_session = await db.get(AuthSession, hash_token(credentials.credentials))
    if auth_session is not None:
        await db.delete(auth_session)
        await db.commit()
    logger.info("auth.logout", user_id=str(user.id))
    return {"status": "ok", "logged_out": True}
