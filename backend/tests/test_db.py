"""Integration tests: application + database (real PostgreSQL)."""

from datetime import datetime

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db import describe_url, ping
from app.models import AppMeta


async def test_engine_ping_against_real_database(database_url: str):
    engine = create_async_engine(database_url)
    try:
        await ping(engine)  # must not raise
    finally:
        await engine.dispose()


async def test_database_round_trip_via_session(migrated_database: str):
    """Insert/select/update/delete on the foundational table."""
    engine = create_async_engine(migrated_database)
    factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            # insert
            session.add(AppMeta(key="test:roundtrip", value="v1"))
            await session.commit()

            # select
            row = await session.get(AppMeta, "test:roundtrip")
            assert row is not None
            assert row.value == "v1"
            assert isinstance(row.updated_at, datetime)
            assert row.updated_at.tzinfo is not None

            # update
            await session.execute(
                update(AppMeta).where(AppMeta.key == "test:roundtrip").values(value="v2")
            )
            await session.commit()
            row = await session.get(AppMeta, "test:roundtrip")
            assert row.value == "v2"

            # delete
            await session.execute(delete(AppMeta).where(AppMeta.key == "test:roundtrip"))
            await session.commit()
            assert await session.get(AppMeta, "test:roundtrip") is None
    finally:
        await engine.dispose()


async def test_describe_url_redacts_password():
    described = describe_url("postgresql+psycopg://floww_user:super-secret@localhost:55432/floww")
    assert "super-secret" not in described
    assert "floww_user" in described
    assert "localhost:55432/floww" in described


async def test_describe_url_without_credentials():
    assert describe_url("postgresql://localhost:5432/db") == ("postgresql://localhost:5432/db")
