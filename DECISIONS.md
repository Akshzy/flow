# ARCHITECTURAL DECISIONS

Record important decisions as:

## ADR-001 — Backend/frontend stack for Phase 1

Date: Phase 1
Status: Accepted

### Context

The repository contained project control documents only (no code, no git
history, no package manifests); the GitHub remote was empty. ARCHITECTURE.md
recommends Next.js/TypeScript/Tailwind (frontend), FastAPI/Python (backend),
PostgreSQL (data).

### Decision

Follow the documented recommendation: FastAPI backend (Python 3.12+,
validated on 3.14) and a Next.js 15 + TypeScript + Tailwind 4 frontend.
### Alternatives

- Node/TypeScript backend (single language): rejected — the architecture
  document explicitly recommends FastAPI; no existing stack conflicted.
- Next.js API routes as the backend: rejected — later phases (webhook
  gateway, queue/worker, AI processing) require a separate backend service.

### Consequences

Two runtimes to install (Python, Node). Python 3.14 wheel availability for
fastapi/sqlalchemy/alembic/psycopg was verified before committing to the
stack. Migrations run through Alembic with the psycopg (v3) driver.

### Evidence

- `git ls-remote https://github.com/Akshzy/flow` → exit 0, no refs (empty repo).
- `pip install --dry-run` resolved cp314 wheels for alembic/psycopg/pytest.
- FastAPI 0.141.1, SQLAlchemy 2.0.54, psycopg 3.3.6, Next.js 15.5.26 in use.

## ADR-002 — Embedded PostgreSQL for development and tests

Date: Phase 1
Status: Accepted

### Context

The development machine (Windows) has no Docker and no PostgreSQL
installation. Phase 1 must verify real application→database, migration→database
and clean-database→migration behavior — against real PostgreSQL per
ARCHITECTURE.md, not SQLite.

### Decision

Provision PostgreSQL binaries via the `embedded-postgres` npm package (dev
dependency at the repository root) and manage the server lifecycle with
`scripts/pg.mjs` (initdb/pg_ctl; the server runs detached; `pg` client used
for readiness checks and database creation). Tests start a fresh cluster per
session (`up --fresh`), so every run verifies migration behavior from a clean
database. `FLOWW_TEST_EXTERNAL_DB=1` switches tests to a provided
`DATABASE_URL` (e.g. a CI PostgreSQL service container).

### Alternatives

- SQLite: rejected — deviates from the documented PostgreSQL data layer.
- Docker/testcontainers: rejected — Docker is unavailable in this environment.
- Hosted PostgreSQL: rejected — would require real credentials.

### Consequences

The `pg.mjs` lifecycle script carries Windows-specific handling (stdio
redirection to avoid detached-server pipe hangs). CI uses the service
container path; the embedded path is used for local dev/test.

### Evidence

- `node scripts/pg.mjs up --json` → FLOWW_PG_JSON with status "running".
- `node scripts/pg.mjs status` after the script exits → running (server
  survives detached).
- pytest session with `up --fresh` → 40/40 tests pass in ~58s.

## ADR-003 — Minimal foundational schema (app_meta) instead of business schema

Date: Phase 1
Status: Accepted

### Context

Phase 1 must implement and verify migrations. The DATA_MODEL.md business
entities (users, tenants, platform_connections, conversations, messages,
orders, ...) belong to Phases 2+; creating them now would violate the
"no future-phase functionality" boundary.

### Decision

Migration 0001 creates a single, minimal, phase-agnostic `app_meta`
(application metadata key/value) table. It establishes the migration
machinery against a real database and verifies application↔database round
trips. SQLAlchemy metadata carries a standard naming convention for
constraints (migrations are deterministic across databases).

### Alternatives

- Zero migrations in Phase 1: rejected — the migration machinery would not be
  verified.
- Full business schema: rejected — future-phase scope.

### Consequences

`app_meta` is small, documented and tested. Business schema arrives in the
phases that require it.

### Evidence

- Clean scratch database → `upgrade head` → `alembic_version` at 0001,
  `app_meta` with key/value/updated_at + PK.
- `upgrade head` repeat (no-op success), `downgrade base` removes `app_meta`
  (alembic_version remains, empty — standard alembic behavior).

## ADR-004 — Error envelope, request IDs and pure ASGI middleware

Date: Phase 1
Status: Accepted

### Context

REQUIREMENTS.md demands structured logs, observable failures and no secret
exposure. Error responses must be consistent. Request correlation needs a
request ID that survives into 500 responses produced by the outer
ServerErrorMiddleware.

### Decision

- Single error envelope: `{"error": {code, message, details?}, "request_id"}`
  for AppError, HTTPException, RequestValidationError (422) and unexpected
  exceptions (500, generic message; stack traces logged server-side only).
- Request IDs: server-generated (client-supplied IDs are not trusted), bound
  to the structlog context per request via a pure ASGI middleware (runs in
  the connection task, so the binding remains visible to outer handlers).
  The context is cleared at request start; request logs contain method, path
  (without query string), status and duration only.
- Logging: structlog with JSON rendering in production/test, console
  rendering in development, and a redaction processor that removes values for
  sensitive keys (password/token/api_key/authorization/credential/cookie/
  private_key/database_url/dsn markers).
- Database URLs are logged with the password component replaced.

### Alternatives

- BaseHTTPMiddleware: rejected — downstream runs in a child task, so the
  bound request ID is not visible to the outer 500 handler.
- FastAPI default error bodies ({detail: ...}): rejected — not consistent.

### Consequences

All API errors share one shape; validation error details are whitelisted
(loc/msg/type only — raw input values, which could contain credentials, are
never echoed).

### Evidence

- tests/test_errors.py: 500 response contains no exception type, no traceback
  and no internal detail; validation errors never leak input values.
- tests/test_logging.py: sensitive keys redacted in rendered JSON output.
- Manual API run: startup log shows `database=postgresql+psycopg://postgres:[REDACTED]@...`.

## ADR-005 — Windows event-loop policy for psycopg async

Date: Phase 1
Status: Accepted

### Context

psycopg's async mode requires a SelectorEventLoop; on Windows the Python
default (and uvicorn's default loop factory) is ProactorEventLoop, which makes
all async database operations fail (psycopg InterfaceError).

### Decision

Install `WindowsSelectorEventLoopPolicy` before any event loop is created:
in tests (conftest) and in the dev server launcher (`scripts/dev.py`, which
also runs uvicorn with `loop="none"` so the policy applies). No policy is set
on other platforms (Linux default is a selector loop).

### Alternatives

- asyncpg driver: rejected — psycopg 3 is the documented driver and its
  conninfo/connect_args handling is already in use.

### Consequences

NOTE: the policy API is deprecated in Python 3.14 (removal slated for
3.16); warnings are suppressed locally and this must be revisited when the
project targets a newer Python or Linux-only hosting (where no policy is
needed). Recorded as a known limitation.

### Evidence

- With ProactorEventLoop: `psycopg.InterfaceError: Psycopg cannot use the
  'ProactorEventLoop' to run in async mode` (observed in test run logs).
- With the selector policy: all 40 tests pass; live uvicorn run connects to
  PostgreSQL at startup.

## ADR-006 — Phase 00 documentation provided without HANDOFF_00

Date: Phase 1
Status: Accepted

### Context

PROJECT_STATUS.md marked Phase 00 as NOT STARTED, but the Phase 00 outputs
(product, requirements, architecture, data model, integrations, webhook spec,
AI policy, test strategy, phases, phase gate, decisions, risks) all exist as
repository documents. No HANDOFF_00.md exists.

### Decision

Treat the provided documents as the Phase 00 baseline input to Phase 1. Do
not fabricate HANDOFF_00.md; record the decision here and reflect reality in
PROJECT_STATUS.md (documents verified to exist; no Phase 00 handoff was
produced by that process).

### Evidence

- All Phase 00 output documents exist in the repository baseline commit.
- HANDOFF_00.md is absent.
