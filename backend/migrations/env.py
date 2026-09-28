"""Alembic migration environment.

The database URL is resolved from the ``DATABASE_URL`` environment variable,
falling back to a local ``backend/.env`` file (via app config). When neither
is available, migrations fail with a clear error.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    # Fall back to the local backend/.env file (loaded by app config).
    try:
        from pydantic import ValidationError

        from app.config import Settings
    except Exception:  # pragma: no cover - import issues are environment problems
        raise RuntimeError(
            "DATABASE_URL is not set and application config could not be imported. "
            "Set the DATABASE_URL environment variable or create backend/.env "
            "from .env.example."
        ) from None
    try:
        return str(Settings().database_url)
    except ValidationError:
        raise RuntimeError(
            "DATABASE_URL is not set (and backend/.env does not provide it). "
            "Set the DATABASE_URL environment variable or create backend/.env "
            "from .env.example."
        ) from None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script output)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direct database connection)."""
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
