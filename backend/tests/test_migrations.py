"""Migration tests: clean database, repeatability, downgrade, failure paths.

These tests run Alembic programmatically. A clean scratch database is created
on the session's PostgreSQL cluster for every test, so migration behavior is
verified from a clean database on every run.
"""

import asyncio
import os
import pathlib
import uuid

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("prepend_sys_path", str(BACKEND_DIR))
    return cfg


def _run_alembic(database_url: str, revision: str, *, direction: str = "upgrade") -> None:
    """Run an alembic upgrade/downgrade against a specific database URL."""
    from alembic import command

    cfg = _alembic_config()
    alembic_command = command.upgrade if direction == "upgrade" else command.downgrade
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        alembic_command(cfg, revision)
    finally:
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url


def _admin_url(database_url: str) -> str:
    return database_url.rsplit("/", 1)[0] + "/postgres"


def _psycopg_url(url: str) -> str:
    """Convert a SQLAlchemy URL to a psycopg-compatible connection string."""
    return url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture()
def scratch_database(database_url: str):
    """Create a fresh scratch database on the session's cluster."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    db_name = f"floww_mig_{uuid.uuid4().hex[:12]}"

    async def _create():
        engine = create_async_engine(_admin_url(database_url), isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        finally:
            await engine.dispose()

    asyncio.run(_create())
    yield database_url.rsplit("/", 1)[0] + f"/{db_name}"

    async def _drop():
        engine = create_async_engine(_admin_url(database_url), isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :db AND pid <> pg_backend_pid()"
                    ),
                    {"db": db_name},
                )
                await conn.execute(text(f'DROP DATABASE "{db_name}"'))
        finally:
            await engine.dispose()

    asyncio.run(_drop())


def test_migration_from_clean_database(scratch_database: str):
    """A clean database can be initialized by running migrations."""
    import psycopg

    _run_alembic(scratch_database, "head")

    # Verify: alembic_version registered, the baseline table exists, and the
    # Phase 2/4/5/6 authentication/tenancy/connection/event/pipeline tables exist.
    with psycopg.connect(_psycopg_url(scratch_database)) as conn, conn.cursor() as cur:
        cur.execute("SELECT version_num FROM alembic_version")
        assert cur.fetchone()[0] == "0007"

        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'app_meta' ORDER BY column_name"
        )
        columns = {row[0] for row in cur.fetchall()}
        assert {"key", "value", "updated_at"} <= columns

        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert {
            "users",
            "tenants",
            "tenant_members",
            "auth_sessions",
            "platform_connections",
            "webhook_events",
            "customers",
            "customer_platform_identities",
            "conversations",
            "messages",
        } <= tables

        cur.execute(
            "SELECT constraint_name FROM information_schema.table_constraints "
            "WHERE table_name = 'app_meta' AND constraint_type = 'PRIMARY KEY'"
        )
        assert cur.fetchone() is not None

        # User email is unique; membership role is constrained to owner/member.
        cur.execute(
            "SELECT constraint_type FROM information_schema.table_constraints "
            "WHERE table_name = 'users' AND constraint_name = 'uq_users_email'"
        )
        assert cur.fetchone()[0] == "UNIQUE"
        cur.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_tenant_members_role'"
        )
        constraint_def = cur.fetchone()[0]
        assert "owner" in constraint_def and "member" in constraint_def


def test_migration_is_repeatable(scratch_database: str):
    """Running migrations again on an already-migrated database succeeds."""
    _run_alembic(scratch_database, "head")  # first run migrates
    _run_alembic(scratch_database, "head")  # second run must be a no-op success

    import psycopg

    with psycopg.connect(_psycopg_url(scratch_database)) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM alembic_version")
        assert cur.fetchone()[0] == 1


def test_downgrade_removes_schema(scratch_database: str):
    """Downgrading to base removes the baseline table and the volume entry.

    Note: alembic keeps the (empty) alembic_version table after downgrading to
    base — standard alembic behavior.
    """
    _run_alembic(scratch_database, "head")
    _run_alembic(scratch_database, "base", direction="downgrade")

    import psycopg

    with psycopg.connect(_psycopg_url(scratch_database)) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'app_meta'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM alembic_version")
        assert cur.fetchone()[0] == 0

    # Re-upgrade so the database is left in a consistent state.
    _run_alembic(scratch_database, "head")


def test_downgrade_to_0001_removes_phase2_tables(scratch_database: str):
    """Rolling back to 0001 removes Phase 2 tables and keeps app_meta."""
    _run_alembic(scratch_database, "head")
    _run_alembic(scratch_database, "0001", direction="downgrade")

    import psycopg

    with psycopg.connect(_psycopg_url(scratch_database)) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert {"users", "tenants", "tenant_members", "auth_sessions"}.isdisjoint(tables)
        assert "app_meta" in tables
        cur.execute("SELECT version_num FROM alembic_version")
        assert cur.fetchone()[0] == "0001"

    # Re-upgrade so the database is left in a consistent state.
    _run_alembic(scratch_database, "head")


def test_app_meta_round_trip_after_migration(scratch_database: str):
    """The foundational table supports real reads/writes after migration."""
    import psycopg

    _run_alembic(scratch_database, "head")
    with psycopg.connect(_psycopg_url(scratch_database)) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO app_meta (key, value) VALUES (%s, %s)",
            ("migration:test", "ok"),
        )
        cur.execute("SELECT value FROM app_meta WHERE key = %s", ("migration:test",))
        assert cur.fetchone()[0] == "ok"
        cur.execute("DELETE FROM app_meta WHERE key = %s", ("migration:test",))


def test_migration_without_configuration_fails_clearly():
    """Missing DATABASE_URL fails with a clear error (no silent success)."""
    from alembic import command

    cfg = _alembic_config()
    old_url = os.environ.pop("DATABASE_URL", None)
    # Ensure no backend/.env provides a fallback either.
    env_file = BACKEND_DIR / ".env"
    backup = None
    if env_file.exists():
        backup = env_file.read_text(encoding="utf-8")
        env_file.unlink()
    try:
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            command.upgrade(cfg, "head")
    finally:
        if old_url is not None:
            os.environ["DATABASE_URL"] = old_url
        if backup is not None:
            env_file.write_text(backup, encoding="utf-8")


def test_migration_with_unreachable_database_fails():
    """A database that cannot be reached makes migrations fail clearly."""
    from alembic import command

    cfg = _alembic_config()
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = (
        "postgresql+psycopg://postgres:postgres@127.0.0.1:1/none?connect_timeout=5"
    )
    try:
        with pytest.raises(Exception) as excinfo:
            command.upgrade(cfg, "head")
        message = str(excinfo.value).lower()
        assert (
            "connect" in message
            or "refused" in message
            or isinstance(excinfo.value.__cause__, OSError)
        )
    finally:
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url
