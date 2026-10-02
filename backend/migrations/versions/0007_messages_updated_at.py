"""messages.updated_at

Phase 7 recovery: the Phase 6 Message model declares an ``updated_at``
column (project convention: every table has created_at/updated_at), but the
Phase 5-era table (migration 0005) does not create it — message inserts
failed with UndefinedColumn. This migration aligns the schema with the
model. Historical migrations are not modified.

Revision ID: 0007
Revises: 0006
Create Date: Phase 7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "updated_at")
