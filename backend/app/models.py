"""Application database models (Phase 1 foundation).

Phase 1 deliberately contains only a minimal, phase-agnostic table:

- ``app_meta``: a generic application metadata key/value table. It exists to
  establish the migration machinery against a real database and to verify
  application ↔ database round trips. The Floww business schema (users,
  tenants, connections, conversations, orders, ...) is introduced in the
  phases that actually require it.

Ownership: ``app_meta`` is application-level (not tenant-scoped) data.
"""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)


class AppMeta(Base):
    """Application-level metadata key/value store."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
