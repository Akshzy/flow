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
- ``auth_sessions``: server-side sessions (hashed opaque token hashes, TTL, logout invalidation);
  users/tenants/tenant_members/auth_sessions schema (migration 0002);
  authorization via server-side membership checks; tenant-scoped queries;
  OWNER/MEMBER roles with a DB CHECK constraint; CORS with explicit origins.

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

from app.extraction import ExtractionStatus

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
        Text,
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE,
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
        Text,
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE,
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
            postgresql_where=text("status IN ('initiated', 'connected')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
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
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ProcessingState(enum.StrEnum):
    """Inbound event lifecycle (Phase 5 gateway; Phase 6 pipeline).

    RECEIVED — accepted into the gateway (transient, in-transaction).
    PENDING_PROCESSING — durably persisted, awaiting Phase 6 processing.
    PROCESSED — normalized downstream (customer/conversation/message
    durable).
    FAILED — a processing attempt recorded a failure (inspectable; retry
    via the bounded processor).
    """

    RECEIVED = "received"
    PENDING_PROCESSING = "pending_processing"
    PROCESSED = "processed"
    FAILED = "failed"


class WebhookEvent(Base):
    """A persisted inbound platform event (Phase 5 gateway).

    - ``dedup_key``: database-level idempotency. Scope:
      ``platform:connection_id:external_event_id`` — tenant-scoped through
      the resolved connection, so equivalent external IDs under different
      connections (tenants) are distinct events.
    - ``raw_payload``: the raw event payload as received (JSONB) — retained
      for Phase 6 processing; never logged.
    - ``tenant_id``/``connection_id``: resolved via server-controlled
      connection mappings — never from client-supplied payload fields.
    """

    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("platform_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    external_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ProcessingState.RECEIVED,
        server_default=ProcessingState.RECEIVED,
    )
    processing_attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    last_processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Customer(Base):
    """A tenant's customer (internal Floww identity — Phase 6).

    Customer identity is NOT a platform identifier: the internal Floww ID is
    the customer identity; platform-specific identity lives in
    ``CustomerPlatformIdentity`` (internal ID + platform identifiers — the
    phone number is not the immutable primary key; BSUID/usernames will
    replace it for username adopters per the verified Meta account-model
    evolution).
    """

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
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


class CustomerPlatformIdentity(Base):
    """Mapping of a Floww customer to a platform identity (Phase 6).

    Uniqueness: one identity per (tenant, platform, external_user_id) —
    enforced at the database level so concurrent deliveries cannot create
    duplicate customers.
    """

    __tablename__ = "customer_platform_identities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    external_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "platform",
            "external_user_id",
            name="uq_customer_platform_identities_identity",
        ),
    )


class ConversationStatus(enum.StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class Conversation(Base):
    """A conversation between a tenant and a customer (Phase 6).

    Resolution is deterministic: one OPEN conversation per
    (tenant, customer, connection) — partial unique index; never based on
    message text or similarity.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        Index(
            "uq_conversations_open",
            "tenant_id",
            "customer_id",
            "connection_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("platform_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ConversationStatus.OPEN,
        server_default=ConversationStatus.OPEN,
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


class Message(Base):
    """A normalized internal message (Phase 6).

    Identity/idempotency: one message per source event — UNIQUE
    ``source_event_id`` at the database level; repeated/concurrent
    processing of the same external event cannot create duplicate messages.

    Trace chain: tenant → connection (via conversation/event) → source event
    → customer → conversation → message.
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("webhook_events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    external_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_timestamp: Mapped[datetime | None] = mapped_column(
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


class OrderExtractionCandidate(Base):
    """A structured order candidate extracted from a message (Phase 7).

    Linked to the source message for traceability. The extraction
    status indicates whether the candidate is ready for seller review
    (EXTRACTED), needs clarification (NEEDS_REVIEW), or is invalid
    (INVALID).
    """

    __tablename__ = "order_extraction_candidates"
    __table_args__ = (
        Index(
            "uq_order_extraction_candidates_message_id",
            "message_id",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The extracted data as JSONB. We store the raw extracted data (as
    # dictated by the AI provider) and then the status is computed from
    # validation and ambiguity detection.
    extracted_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ExtractionStatus.INVALID,
        server_default=ExtractionStatus.INVALID,
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


class OrderStatus(enum.StrEnum):
    """The authoritative order lifecycle (DATA_MODEL.md; enforced by the
    application's state machine and tested).

    NEW → (NEEDS_REVIEW) → CONFIRMED → PROCESSING → COMPLETED
    CANCELLED / FAILED — terminal states.
    """

    NEW = "new"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Order(Base):
    """A tenant-owned order (Phase 8) created deterministically from a
    verified extraction candidate.

    Idempotency: UNIQUE ``extraction_candidate_id`` — one order per
    candidate, enforced at the database level (repeated/concurrent
    conversion cannot create duplicate orders).

    The seller remains authoritative: no automatic confirmation,
    processing, or completion happens anywhere.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extraction_candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("order_extraction_candidates.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=OrderStatus.NEW,
        server_default=OrderStatus.NEW,
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


class OrderItem(Base):
    """An order item — preserves the Phase 7 structured extraction result.

    Quantities never silently change; products never silently disappear:
    the seller's explicit edit (recorded in the audit trail) is the only
    mutation path.
    """

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    variant: Mapped[str | None] = mapped_column(Text, nullable=True)
    size: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OrderEvent(Base):
    """Append-only audit trail for the order lifecycle (Phase 8).

    Records order creation, edits and every status transition with the
    acting user. Never logs secrets or message bodies.
    """

    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
