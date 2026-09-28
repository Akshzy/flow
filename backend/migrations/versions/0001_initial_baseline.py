"""initial baseline: app_meta table

Phase 1 foundation migration. Establishes the migration machinery against a
real database with a minimal, phase-agnostic application metadata table
(``app_meta``) used to verify database connectivity and migrations.

The Floww business schema (users, tenants, connections, conversations,
messages, orders, ...) is introduced in the phases that require it.

Revision ID: 0001
Revises:
Create Date: Phase 1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_meta",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_meta")),
    )


def downgrade() -> None:
    op.drop_table("app_meta")
