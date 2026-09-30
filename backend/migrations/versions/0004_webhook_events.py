"""webhook_events

Phase 5 — inbound webhook gateway:

- dedup_key (UNIQUE): database-level idempotency. Scope:
  platform:connection_id:external_event_id — tenant-scoped through the
  resolved connection.
- raw_payload (JSONB): the raw event as received, retained for Phase 6
  processing; never logged.
- tenant_id / connection_id: resolved via server-controlled connection
  mappings — never from client-supplied payload fields.
- lifecycle: received → pending_processing (→ failed for recorded
  processing failures).

Revision ID: 0004
Revises: 0003
Create Date: Phase 5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_event_id", sa.Text(), nullable=True),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("external_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "processing_state",
            sa.Text(),
            server_default="received",
            nullable=False,
        ),
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_processing_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["platform_connections.id"],
            name=op.f("fk_webhook_events_connection_id_platform_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_webhook_events_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_webhook_events_dedup_key")),
        sa.CheckConstraint(
            "processing_state IN ('received', 'pending_processing', 'failed')",
            name=op.f("ck_webhook_events_processing_state"),
        ),
    )
    op.create_index(
        op.f("ix_webhook_events_connection_id"),
        "webhook_events",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_events_tenant_id"),
        "webhook_events",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_webhook_events_tenant_id"), table_name="webhook_events"
    )
    op.drop_index(
        op.f("ix_webhook_events_connection_id"), table_name="webhook_events"
    )
    op.drop_table("webhook_events")
