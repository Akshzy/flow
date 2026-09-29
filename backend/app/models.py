"""Application database models.

Phase 1 foundation (phase-agnostic):

- ``app_meta``: application metadata key/value table used to establish the
  migration machinery and verify database round trips.

Phase 2 — authentication and multi-tenancy:

- ``users``: Floww user identity (email + argon2id password hash + status).
- ``tenants``: an independent business/account — the primary isolation
  boundary.
- ``tenant_members``: membership of a user in a tenant with a role
  (owner/member). Every tenant-access decision is based on this table.
- ``auth_sessions``: server-side sessions (hashed opaque token + expiry).

Later phases (connections, conversations, messages, orders, ...) add
tenant-owned entities with an explicit tenant relationship.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    MetaData,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)


class UserStatus(enum.StrEnum):
    ACTIVE = "active"


class Role(enum.StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class AppMeta(Base):
    """Application-level metadata key/value store."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base):
    """A Floww user identity. Passwords are stored as argon2id hashes only."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=UserStatus.ACTIVE, server_default=UserStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Tenant(Base):
    """An independent business/account — the primary isolation boundary."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=UserStatus.ACTIVE, server_default=UserStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMember(Base):
    """Membership of a user in a tenant. The authorization source of truth."""

    __tablename__ = "tenant_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_members_tenant_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=Role.MEMBER,
        server_default=Role.MEMBER,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuthSession(Base):
    """Server-side session. Only the SHA-256 hash of the token is stored."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class Platform(enum.StrEnum):
    WHATSAPP = "whatsapp"


class ConnectionStatus(enum.StrEnum):
    INITIATED = "initiated"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class PlatformConnection(Base):
    """A tenant-owned connection to a messaging platform (Phase 4: WhatsApp).

    Identifier model (Meta account model is evolving — see DECISIONS.md
    ADR-011 and INTEGRATIONS.md):

    - ``waba_id``: WhatsApp Business Account ID (verified current Meta
      behavior; the account unit the account-model evolution splits into
      WAAC/PMA).
    - ``phone_number_id``: phone number ID (verified current Meta behavior).
    - ``account_identifiers``: JSONB extension point for identifiers from
      the verified evolving account model (WAAC/PMA) and future platform
      identifiers — avoids inventing columns for unverified field names.

    ``credentials_encrypted`` holds Fernet-encrypted credential material
    (real encryption; the plaintext never touches the database).

    Lifecycle: initiated → connected → disconnected. Disconnected rows are
    kept (history) and excluded from the partial unique index, so a tenant
    can reconnect (new row) — one active connection per (tenant, platform).
    """

    __tablename__ = "platform_connections"
    __table_args__ = (
        Index(
            "uq_platform_connections_active",
            "tenant_id",
            "platform",
            unique=True,
            postgresql_where=text(
                "status IN ('initiated', 'connected')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=Platform.WHATSAPP,
        server_default=Platform.WHATSAPP,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ConnectionStatus.INITIATED,
        server_default=ConnectionStatus.INITIATED,
    )
    waba_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_identifiers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    credentials_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    initiated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
