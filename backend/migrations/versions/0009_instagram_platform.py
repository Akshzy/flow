"""platform_connections.platform includes instagram

Phase 9 — Instagram integration: extend the connection platform CHECK from
'whatsapp'-only to include 'instagram'. The connection model's other
guarantees (tenant ownership, the partial unique index over ACTIVE
connections per (tenant, platform), lifecycle) are unchanged — Instagram
connections reuse the existing abstraction.

Revision ID: 0009
Revises: 0008
Create Date: Phase 9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # op.f() marks the constraint name as final (no naming-convention
    # re-application).
    op.drop_constraint(
        op.f("ck_platform_connections_platform"),
        "platform_connections",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_platform_connections_platform"),
        "platform_connections",
        "platform IN ('whatsapp', 'instagram')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_platform_connections_platform"),
        "platform_connections",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_platform_connections_platform"),
        "platform_connections",
        "platform = 'whatsapp'",
    )
