"""Test configuration and fixtures.

Database strategy: tests run against a real PostgreSQL server (binaries
provisioned via the ``embedded-postgres`` npm package at the repository root,
managed by ``scripts/pg.mjs``). A fresh cluster is started per test session
(``up --fresh``), so every run verifies migration behavior from a clean
database.

Set ``FLOWW_TEST_EXTERNAL_DB=1`` to skip the embedded server and use a
provider-supplied ``DATABASE_URL`` (e.g. a CI PostgreSQL service container).
"""

import asyncio
import contextlib
import json
import os
import pathlib
import subprocess
import sys

import pytest

# On Windows, psycopg's async mode requires a SelectorEventLoop (the Python
# default is ProactorEventLoop). Install the selector policy before any event
# loop is created; this is a no-op on other platforms.
# NOTE: the policy API is deprecated in Python 3.14 (removal slated for
# 3.16); revisit when the project targets a newer Python or Linux-only hosting.
if sys.platform == "win32":
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parents[0]

# backend package must be importable from tests
sys.path.insert(0, str(BACKEND_DIR))

# Test-cluster configuration (independent from the dev instance).
TEST_PG = {
    "PG_DATA_DIR": str(REPO_ROOT / ".pgdata" / "test"),
    "PG_PORT": "55433",
    "PG_USER": "postgres",
    "PG_PASSWORD": "postgres",
    "PG_DATABASE": "floww_test",
}


def _run_pg(*pg_args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(REPO_ROOT / "scripts" / "pg.mjs"), *pg_args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
        env={**os.environ, **TEST_PG},
    )


def _parse_pg_json(output: str) -> dict:
    for line in output.splitlines():
        if line.startswith("FLOWW_PG_JSON: "):
            return json.loads(line.removeprefix("FLOWW_PG_JSON: "))
    raise RuntimeError(
        "scripts/pg.mjs did not report FLOWW_PG_JSON connection info. "
        f"stdout/stderr: {output[:500]}"
    )


@pytest.fixture(scope="session", autouse=True)
def database_url() -> str:
    """Provide DATABASE_URL for the whole test session.

    Starts a fresh embedded PostgreSQL cluster (clean database) unless an
    external database is supplied. Fails clearly if the database cannot be
    started.
    """
    if os.environ.get("FLOWW_TEST_EXTERNAL_DB") == "1":
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("FLOWW_TEST_EXTERNAL_DB=1 but DATABASE_URL is not set.")
        yield url
        return

    result = _run_pg("up", "--fresh", "--json")
    if result.returncode != 0:
        raise RuntimeError(
            "Embedded PostgreSQL failed to start. "
            f"stdout: {result.stdout[:300]} stderr: {result.stderr[:300]}"
        )
    info = _parse_pg_json(result.stdout)
    url = (
        f"postgresql+psycopg://{info['user']}:{info['password']}"
        f"@{info['host']}:{info['port']}/{info['database']}"
    )
    os.environ["DATABASE_URL"] = url
    yield url

    # Teardown: stop the embedded server (best effort).
    with contextlib.suppress(subprocess.SubprocessError, OSError):
        _run_pg("down", timeout=60)


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    """Run migrations once per session against the test database."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("prepend_sys_path", str(BACKEND_DIR))
    command.upgrade(cfg, "head")
    return database_url


@pytest.fixture()
def app_settings(database_url: str):
    from app.config import Settings

    return Settings()


@pytest.fixture()
async def client(app_settings):
    """HTTP test client bound to the real app, with lifespan executed."""
    import httpx

    from app.main import create_app

    application = create_app(settings=app_settings)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as test_client:
            yield test_client
