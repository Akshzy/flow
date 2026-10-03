"""response_drafts, response_events, tenants.responses_enabled

Phase 10 — controlled seller responses:

- response_drafts: the response lifecycle (draft -> approved -> sent /
  failed); intent classification (deterministic); origin (ai_suggested /
  seller_written); send attempts/errors. The seller's explicit approval is
  the only path to send — no automatic AI -> send transition.
- response_events: append-only audit trail for the response lifecycle.
- tenants.responses_enabled: the tenant-level opt-in control (responses
  cannot be sent while disabled).

Revision ID: 0010
Revises: 0009
Create Date: Phase 10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "response_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), server_default="ai_suggested", nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("send_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_send_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_response_drafts_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_response_drafts_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_response_drafts_order_id_orders"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_response_drafts_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_response_drafts")),
        sa.CheckConstraint(
            "intent IN ('order_confirmation', 'unsupported', 'unknown')",
            name=op.f("ck_response_drafts_intent"),
        ),
        sa.CheckConstraint(
            "origin IN ('ai_suggested', 'seller_written')",
            name=op.f("ck_response_drafts_origin"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'sent', 'failed')",
            name=op.f("ck_response_drafts_status"),
        ),
    )
    op.create_index(
        op.f("ix_response_drafts_tenant_id"),
        "response_drafts",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_response_drafts_conversation_id"),
        "response_drafts",
        ["conversation_id"],
        unique=False,
    )
    op.create_table(
        "response_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("response_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["response_id"],
            ["response_drafts.id"],
            name=op.f("fk_response_events_response_id_response_drafts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_response_events_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_response_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_response_events")),
    )
    op.create_index(
        op.f("ix_response_events_response_id"),
        "response_events",
        ["response_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_response_events_tenant_id"),
        "response_events",
        ["tenant_id"],
        unique=False,
    )
    # The tenant-level opt-in control.
    op.add_column(
        "tenants",
        sa.Column(
            "responses_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "responses_enabled")
    op.drop_index(
        op.f("ix_response_events_tenant_id"), table_name="response_events"
    )
    op.drop_index(
        op.f("ix_response_events_response_id"), table_name="response_events"
    )
    op.drop_table("response_events")
    op.drop_index(
        op.f("ix_response_drafts_conversation_id"), table_name="response_drafts"
    )
    op.drop_index(
        op.f("ix_response_drafts_tenant_id"), table_name="response_drafts"
    )
    op.drop_table("response_drafts")
