"""orders, order_items, order_events

Phase 8 — order management:

- orders: tenant-owned; UNIQUE extraction_candidate_id (one order per
  candidate — database-level idempotency); the authoritative lifecycle
  status (NEW/NEEDS_REVIEW/CONFIRMED/PROCESSING/COMPLETED/CANCELLED/FAILED).
- order_items: preserve the Phase 7 structured extraction result
  (product/quantity/variant/size/color); no price fields (none exist in the
  extraction contract — nothing is invented).
- order_events: append-only audit trail for the order lifecycle.

Revision ID: 0008
Revises: 0007
Create Date: Phase 8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), server_default="new", nullable=False),
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
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_orders_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_candidate_id"],
            ["order_extraction_candidates.id"],
            name=op.f("fk_orders_extraction_candidate_id_order_extraction_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_orders_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_orders_conversation_id_conversations"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint(
            "extraction_candidate_id",
            name=op.f("uq_orders_extraction_candidate_id"),
        ),
        sa.CheckConstraint(
            "status IN ('new', 'needs_review', 'confirmed', 'processing', "
            "'completed', 'cancelled', 'failed')",
            name=op.f("ck_orders_status"),
        ),
    )
    op.create_index(op.f("ix_orders_tenant_id"), "orders", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_orders_customer_id"), "orders", ["customer_id"], unique=False
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=True),
        sa.Column("size", sa.Text(), nullable=True),
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_order_items_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_order_items_quantity_positive")
        ),
    )
    op.create_index(
        op.f("ix_order_items_order_id"), "order_items", ["order_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_items_tenant_id"), "order_items", ["tenant_id"], unique=False
    )
    op.create_table(
        "order_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
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
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_events_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_order_events_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_order_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_events")),
    )
    op.create_index(
        op.f("ix_order_events_order_id"), "order_events", ["order_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_events_tenant_id"), "order_events", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_order_events_tenant_id"), table_name="order_events"
    )
    op.drop_index(op.f("ix_order_events_order_id"), table_name="order_events")
    op.drop_table("order_events")
    op.drop_index(
        op.f("ix_order_items_tenant_id"), table_name="order_items"
    )
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_table("order_items")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_tenant_id"), table_name="orders")
    op.drop_table("orders")
