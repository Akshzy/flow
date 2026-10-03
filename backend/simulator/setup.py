"""TEST-ONLY fixture mechanism: create the connected connection the
simulator's fixtures map to.

The Phase 04 connection model does not permit real connected assets yet
(the Meta authorization flow is not implemented), so this TEST-ONLY
mechanism creates the deterministic connected connection (stable fake WABA /
phone_number_id matching ``simulator.fixtures``) via the database layer.

This is NOT a production API: nothing here is exposed over HTTP, and no
production endpoint lets callers arbitrarily mark connections as authorized.
The tenant, user and connection use stable fake identifiers and are created
only if missing (idempotent).
"""

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from app.models import (
    ConnectionStatus,
    Platform,
    PlatformConnection,
    Role,
    Tenant,
    TenantMember,
    User,
)
from app.security import hash_password
from simulator.fixtures import (
    CONNECTION_PHONE_NUMBER_ID,
    CONNECTION_WABA_ID,
    INSTAGRAM_PHONE_NUMBER_ID,
)

logger = structlog.get_logger("simulator.setup")

# Stable fake identifiers (deterministic across runs; fake).
FIXTURE_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-00000000a001")
FIXTURE_USER_ID = uuid.UUID("00000000-0000-0000-0000-00000000b001")
FIXTURE_EMAIL = "simulator-fixture@example.com"
FIXTURE_TENANT_NAME = "Simulator Fixture Business"
FIXTURE_PASSWORD = "simulator-fixture-password"  # fake; local test only


async def create_fixture_connection(session) -> PlatformConnection:
    """Create (or reuse) the deterministic connected fixture connection."""
    # Tenant
    tenant = await session.get(Tenant, FIXTURE_TENANT_ID)
    if tenant is None:
        tenant = Tenant(id=FIXTURE_TENANT_ID, name=FIXTURE_TENANT_NAME)
        session.add(tenant)
        await session.flush()

    # User
    user = await session.get(User, FIXTURE_USER_ID)
    if user is None:
        user = User(
            id=FIXTURE_USER_ID,
            email=FIXTURE_EMAIL,
            password_hash=hash_password(FIXTURE_PASSWORD),
        )
        session.add(user)
        await session.flush()

    # OWNER membership for the fixture user
    existing_membership = await session.execute(
        select(TenantMember).where(
            TenantMember.tenant_id == FIXTURE_TENANT_ID,
            TenantMember.user_id == FIXTURE_USER_ID,
        )
    )
    if existing_membership.scalars().first() is None:
        session.add(
            TenantMember(
                tenant_id=FIXTURE_TENANT_ID,
                user_id=FIXTURE_USER_ID,
                role=Role.OWNER,
            )
        )

    # Connected WhatsApp connection (stable identifiers match the fixtures).
    existing_connection = await session.execute(
        select(PlatformConnection).where(
            PlatformConnection.tenant_id == FIXTURE_TENANT_ID,
            PlatformConnection.platform == Platform.WHATSAPP,
            PlatformConnection.status == ConnectionStatus.CONNECTED,
        )
    )
    connection = existing_connection.scalars().first()
    if connection is None:
        connection = PlatformConnection(
            tenant_id=FIXTURE_TENANT_ID,
            platform=Platform.WHATSAPP,
            status=ConnectionStatus.CONNECTED,
            waba_id=CONNECTION_WABA_ID,
            phone_number_id=CONNECTION_PHONE_NUMBER_ID,
            connected_by_user_id=FIXTURE_USER_ID,
            connected_at=datetime.now(UTC),
        )
        session.add(connection)
        await session.flush()

    # Connected Instagram connection (Phase 9; same lifecycle abstraction).
    # The check covers ACTIVE (initiated/connected) states — the partial
    # unique index occupies the slot for both; an INITIATED connection is
    # transitioned to CONNECTED (the fixture fakes the authorization
    # completion).
    existing_ig = await session.execute(
        select(PlatformConnection).where(
            PlatformConnection.tenant_id == FIXTURE_TENANT_ID,
            PlatformConnection.platform == Platform.INSTAGRAM,
            PlatformConnection.status.in_([ConnectionStatus.INITIATED, ConnectionStatus.CONNECTED]),
        )
    )
    ig_connection = existing_ig.scalars().first()
    if ig_connection is None:
        session.add(
            PlatformConnection(
                tenant_id=FIXTURE_TENANT_ID,
                platform=Platform.INSTAGRAM,
                status=ConnectionStatus.CONNECTED,
                phone_number_id=INSTAGRAM_PHONE_NUMBER_ID,
                connected_by_user_id=FIXTURE_USER_ID,
                connected_at=datetime.now(UTC),
            )
        )
        await session.flush()
    elif ig_connection.status == ConnectionStatus.INITIATED:
        # Fake the authorization completion for the initiated connection —
        # WITH the fixture identifier (the initiated record has none).
        ig_connection.status = ConnectionStatus.CONNECTED
        ig_connection.phone_number_id = INSTAGRAM_PHONE_NUMBER_ID
        ig_connection.connected_at = datetime.now(UTC)
        await session.flush()

    await session.commit()
    logger.info(
        "simulator.fixture_connection_ready",
        tenant_id=str(FIXTURE_TENANT_ID),
        connection_id=str(connection.id),
    )
    return connection


def ensure_fixture_connection(database_url: str) -> str:
    """Synchronously create the fixture connection; returns the connection id."""
    # On Windows, psycopg's async mode requires a SelectorEventLoop (the
    # Python default is ProactorEventLoop) — same policy as tests/dev.py.
    import sys

    if sys.platform == "win32":
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async def _run() -> str:
        engine = create_async_engine(database_url)
        try:
            factory = async_sessionmaker(bind=engine, expire_on_commit=False)
            async with factory() as session:
                connection = await create_fixture_connection(session)
                return str(connection.id)
        finally:
            await engine.dispose()

    return asyncio.run(_run())
