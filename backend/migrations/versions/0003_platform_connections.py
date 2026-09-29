"""platform_connections

Phase 4 — WhatsApp connection (tenant-owned platform connection):

- identifier fields supported by verified current Meta behavior: waba_id,
  phone_number_id; account_identifiers (JSONB) is the extension point for
  the verified evolving account model (WABA → WAAC + PMA split) without
  inventing columns for unverified field names.
- credentials_encrypted: Fernet-encrypted credential material (plaintext
  never stored).
- lifecycle: initiated → connected → disconnected; a partial unique index
  allows at most ONE active (initiated/connected) connection per
  (tenant, platform) — disconnected rows are kept as history and excluded
  from the index so a tenant can reconnect.

Revision ID: 0003
Revises: 0002
Create Date: Phase 4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.Text(), server_default="whatsapp", nullable=False),
        sa.Column("status", sa.Text(), server_default="initiated", nullable=False),
        sa.Column("waba_id", sa.Text(), nullable=True),
        sa.Column("phone_number_id", sa.Text(), nullable=True),
        sa.Column("account_identifiers", sa.JSON(), nullable=True),
        sa.Column("credentials_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("connected_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_platform_connections_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connected_by_user_id"],
            ["users.id"],
            name=op.f("fk_platform_connections_connected_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_connections")),
        sa.CheckConstraint(
            "status IN ('initiated', 'connected', 'disconnected')",
            name=op.f("ck_platform_connections_status"),
        ),
        sa.CheckConstraint(
            "platform = 'whatsapp'", name=op.f("ck_platform_connections_platform")
        ),
    )
    op.create_index(
        op.f("ix_platform_connections_tenant_id"),
        "platform_connections",
        ["tenant_id"],
        unique=False,
    )
    # One ACTIVE connection per (tenant, platform); disconnected history rows
    # are excluded so a tenant can reconnect.
    op.create_index(
        "uq_platform_connections_active",
        "platform_connections",
        ["tenant_id", "platform"],
        unique=True,
        postgresql_where=sa.text("status IN ('initiated', 'connected')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_platform_connections_active", table_name="platform_connections"
    )
    op.drop_index(
        op.f("ix_platform_connections_tenant_id"), table_name="platform_connections"
    )
    op.drop_table("platform_connections")
