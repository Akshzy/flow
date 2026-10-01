"""customers, customer_platform_identities, conversations, messages

Phase 6 — deterministic message pipeline:

- customers: internal Floww customer identity (tenant-owned).
- customer_platform_identities: customer ↔ platform identity mapping;
  UNIQUE (tenant, platform, external_user_id) — database-level protection
  against concurrent duplicate customers. Phone number is not the identity
  key (BSUID-aware per the verified Meta account-model evolution).
- conversations: one OPEN conversation per (tenant, customer, connection) —
  partial unique index; never text/similarity-based.
- messages: one message per source event — UNIQUE source_event_id;
  deterministic message identity/idempotency.
- webhook_events.processing_state CHECK extended with 'processed'.

Revision ID: 0005
Revises: 0004
Create Date: Phase 6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_customers_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index(
        op.f("ix_customers_tenant_id"), "customers", ["tenant_id"], unique=False
    )
    op.create_table(
        "customer_platform_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_platform_identities_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_customer_platform_identities_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_platform_identities")),
        sa.UniqueConstraint(
            "tenant_id",
            "platform",
            "external_user_id",
            name="uq_customer_platform_identities_identity",
        ),
    )
    op.create_index(
        op.f("ix_customer_platform_identities_customer_id"),
        "customer_platform_identities",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_platform_identities_tenant_id"),
        "customer_platform_identities",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["platform_connections.id"],
            name=op.f("fk_conversations_connection_id_platform_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_conversations_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_conversations_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        sa.CheckConstraint(
            "status IN ('open', 'closed')", name=op.f("ck_conversations_status")
        ),
    )
    op.create_index(
        op.f("ix_conversations_tenant_id"),
        "conversations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_customer_id"),
        "conversations",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_connection_id"),
        "conversations",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        "uq_conversations_open",
        "conversations",
        ["tenant_id", "customer_id", "connection_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("source_event_id", sa.Uuid(), nullable=False),
        sa.Column("external_event_id", sa.Text(), nullable=True),
        sa.Column("message_type", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("external_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_messages_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["webhook_events.id"],
            name=op.f("fk_messages_source_event_id_webhook_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_messages_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint(
            "source_event_id", name=op.f("uq_messages_source_event_id")
        ),
    )
    op.create_index(
        op.f("ix_messages_tenant_id"), "messages", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_messages_conversation_id"),
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_messages_customer_id"), "messages", ["customer_id"], unique=False
    )
    # Extend the Phase 5 processing-state CHECK with 'processed'. op.f()
    # marks the constraint name as final (no naming-convention re-application).
    op.drop_constraint(
        op.f("ck_webhook_events_processing_state"), "webhook_events", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_webhook_events_processing_state"),
        "webhook_events",
        "processing_state IN ('received', 'pending_processing', 'processed', 'failed')",
    )


def downgrade() -> None:
    # Restore the Phase 5 processing-state CHECK.
    op.drop_constraint(
        op.f("ck_webhook_events_processing_state"), "webhook_events", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_webhook_events_processing_state"),
        "webhook_events",
        "processing_state IN ('received', 'pending_processing', 'failed')",
    )
    op.drop_index(
        op.f("ix_messages_customer_id"), table_name="messages"
    )
    op.drop_index(
        op.f("ix_messages_conversation_id"), table_name="messages"
    )
    op.drop_index(op.f("ix_messages_tenant_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index("uq_conversations_open", table_name="conversations")
    op.drop_index(
        op.f("ix_conversations_connection_id"), table_name="conversations"
    )
    op.drop_index(
        op.f("ix_conversations_customer_id"), table_name="conversations"
    )
    op.drop_index(op.f("ix_conversations_tenant_id"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(
        op.f("ix_customer_platform_identities_tenant_id"),
        table_name="customer_platform_identities",
    )
    op.drop_index(
        op.f("ix_customer_platform_identities_customer_id"),
        table_name="customer_platform_identities",
    )
    op.drop_table("customer_platform_identities")
    op.drop_index(op.f("ix_customers_tenant_id"), table_name="customers")
    op.drop_table("customers")
