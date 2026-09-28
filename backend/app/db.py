"""Database foundation: async engine creation and connectivity checks."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str | Any) -> AsyncEngine:
    """Create the async SQLAlchemy engine for the application.

    ``pool_pre_ping`` ensures stale connections are detected and replaced,
    so a database restart does not leave the application with dead handles.
    Accepts a URL string (or anything string-coercible, e.g. pydantic Dsn).
    """
    return create_async_engine(
        str(database_url),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        # Bound connection attempts so a database outage fails within seconds
        # instead of hanging requests indefinitely (libpq connect_timeout).
        connect_args={"connect_timeout": 5},
    )


async def ping(engine: AsyncEngine) -> None:
    """Verify database connectivity with a minimal round trip.

    Raises any driver/connection exception to the caller; callers decide
    how to report the failure (readiness endpoint, startup log, ...).
    """
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the request-scoped session factory for the application.

    ``expire_on_commit=False`` so attributes stay readable after commit
    (response building does not trigger extra refresh queries).
    """
    return async_sessionmaker(bind=engine, expire_on_commit=False)


def describe_url(database_url: Any) -> str:
    """Return a log-safe description of a database URL.

    The password component is replaced so database credentials never appear
    in logs.
    """
    text_url = str(database_url)
    if "@" not in text_url:
        return text_url
    scheme_split = text_url.split("://", 1)
    if len(scheme_split) != 2:
        return text_url
    scheme, rest = scheme_split
    userinfo, _, host = rest.rpartition("@")
    if ":" in userinfo:
        userinfo = userinfo.split(":", 1)[0] + ":[REDACTED]"
    elif userinfo:
        userinfo = userinfo + ":[REDACTED]"
    return f"{scheme}://{userinfo}@{host}"
