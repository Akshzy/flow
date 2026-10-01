"""order_extraction_candidate table

Phase 7 — AI order extraction: add table for storing extraction candidates.

Revision ID: 0006
Revises: 0005
Create Date: Phase 7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_extraction_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            nullable=True,
        ),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column(
            "extracted_data",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="invalid",
        ),
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
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_order_extraction_candidates_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_order_extraction_candidates_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_order_extraction_candidates_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_extraction_candidates")),
        sa.UniqueConstraint(
            "message_id",
            name=op.f("uq_order_extraction_candidates_message_id"),
        ),
        sa.CheckConstraint(
            "status IN ('extracted', 'needs_review', 'invalid')",
            name=op.f("ck_order_extraction_candidates_status"),
        ),
    )
    op.create_index(
        op.f("ix_order_extraction_candidates_tenant_id"),
        "order_extraction_candidates",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_extraction_candidates_conversation_id"),
        "order_extraction_candidates",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_extraction_candidates_message_id"),
        "order_extraction_candidates",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_order_extraction_candidates_message_id"),
        table_name="order_extraction_candidates",
    )
    op.drop_index(
        op.f("ix_order_extraction_candidates_conversation_id"),
        table_name="order_extraction_candidates",
    )
    op.drop_index(
        op.f("ix_order_extraction_candidates_tenant_id"),
        table_name="order_extraction_candidates",
    )
    op.drop_constraint(
        op.f("ck_order_extraction_candidates_status"),
        "order_extraction_candidates",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_order_extraction_candidates_message_id_messages"),
        "order_extraction_candidates",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_order_extraction_candidates_conversation_id_conversations"),
        "order_extraction_candidates",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_order_extraction_candidates_tenant_id_tenants"),
        "order_extraction_candidates",
        type_="foreignkey",
    )
    op.drop_table("order_extraction_candidates")