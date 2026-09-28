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

## ADR-007 — Password authentication with argon2id and opaque server-side sessions

Date: Phase 2
Status: Accepted

### Context

Phase 2 requires Floww user authentication (not Meta authentication, which
belongs to Phases 03/04). Requirements: secure authentication, session/token
validation, logout/invalidation, no plaintext passwords, no custom
cryptography.

### Decision

- Email + password registration; passwords hashed with argon2id
  (argon2-cffi, OWASP-recommended; library defaults m=64MiB/t=3/p=4).
- Server-side sessions with opaque bearer tokens: `secrets.token_urlsafe(32)`
  tokens returned to the client, only the SHA-256 hash persisted
  (`auth_sessions.token_hash`, indexed by `expires_at`); expiry enforced at
  lookup (401 `session_expired`, distinct from 401 `unauthorized`).
- Logout deletes the session row server-side (immediate invalidation).
- Unknown email and wrong password return the identical generic 401
  `invalid_credentials` (no account enumeration).

### Alternatives

- JWTs: rejected for Phase 2 — invalidation requires a denylist; opaque
  sessions give real invalidation without a token-signing secret.
- passlib/bcrypt: rejected — passlib is unmaintained (bcrypt 4.x
  incompatibilities); argon2-cffi is current and has verified Python 3.14
  wheels.
- Cookies (httpOnly): rejected for Phase 2 — cross-origin cookie handling
  requires CORS-with-credentials and CSRF protection; bearer tokens avoid
  both. If cookies are introduced later, cookie security and CSRF become
  mandatory work (Phase 13 hardening).

### Consequences

Tokens live in browser localStorage (XSS-exposed; mitigated by standard
Next.js/React escaping; recorded as a known limitation for Phase 13).
Expired session rows are not removed on access (lazy cleanup deferred to
Phase 13 hardening).

### Evidence

- tests/test_security.py: argon2id format, salted/unique hashes,
  verify correct/wrong/malformed, token randomness, hash≠token.
- tests/test_auth.py: 20 auth tests incl. password-hash-at-rest DB check,
  expired session → 401 session_expired, logout invalidation (token unusable,
  other sessions survive), no password in logs.
- Live run: register → 201, login → 200 token, logout → token unusable (401).

## ADR-008 — Tenant object as the Phase 2 isolation resource; 403/404 distinction

Date: Phase 2
Status: Accepted

### Context

Phase 2 must prove tenant isolation with cross-tenant GET/UPDATE/DELETE and
direct-object-ID attacks. DATA_MODEL's tenant-owned business resources
(connections, conversations, orders, ...) belong to later phases; inventing a
placeholder resource would violate the phase boundary.

### Decision

- The TENANT itself is the first tenant-owned resource:
  - `GET /tenants` — tenant-scoped list (only the caller's tenants, via a
    membership join filtered by user_id).
  - `GET /tenants/{id}` — requires membership (404 missing, 403 non-member).
  - `PATCH /tenants/{id}` — OWNER only (rename).
  - `DELETE /tenants/{id}` — OWNER only (DB-level ON DELETE CASCADE removes
    memberships).
- Status codes: 401 unauthorized (missing/invalid/expired token, login
  failure via `invalid_credentials`), 403 forbidden (exists but no access /
  wrong role), 404 not_found (missing tenant), 409 conflict (duplicate
  email), 422 validation_error.
- Tenant existence is revealed to authenticated users only (403 for
  non-members); tenant IDs are uuid4 (unguessable), so enumeration is
  impractical.

### Alternatives

- 404 for non-members (hide tenant existence): rejected — the phase requires
  distinguishing 401/403/404; uuid4 IDs make enumeration impractical.
- A generic tenant-owned placeholder resource: rejected — future-phase scope.

### Consequences

Roles limited to OWNER/MEMBER (no premature RBAC). The role column carries a
DB CHECK constraint (`owner`/`member` only) — invalid roles are rejected by
the database.

### Evidence

- tests/test_isolation.py: full matrix (A→A allowed, B→B allowed, A→B denied
  for GET/PATCH/DELETE, B→A denied, member role restrictions, forged UUID →
  404, list scoping, data-layer IDOR checks, deleted tenant revokes access).
- tests/test_tenants.py: role CHECK constraint rejects 'admin' at the DB level.
- Live run: A→A 200; A→B GET/PATCH/DELETE 403; B→A 403; no token 401.

## ADR-009 — Privacy policy rendering from FLOWW_PRIVACY_POLICY.md; no speculative Meta configuration

Date: Phase 3 (overnight run)
Status: Accepted

### Context

Meta app review requires a publicly accessible privacy policy URL. The owner
provided `FLOWW_PRIVACY_POLICY.md` at the repository root as the authoritative
policy. The overnight-run scope forbids all Meta-specific implementation
(OAuth, Embedded Signup, webhooks) — so no Phase 3 component requires Meta
secrets yet.

### Decision

- `/privacy` is a server component (no client JavaScript) rendering the
  complete policy faithfully: all 17 sections, substantive statements,
  and the seven [TO BE COMPLETED] placeholders preserved verbatim and
  styled distinctly (amber highlight) so incomplete information is never
  mistaken for real contact details.
- A minimal footer link to /privacy was added to the root layout (purely
  additive rendering; no Phase 2 behavior changed).
- NO Meta environment variables were added to .env.example: no implemented
  Phase 3 component requires a secret, and the prompt forbids speculative
  configuration. Meta configuration (app id/secret, tokens, verify token)
  will be added by the phase that actually implements the component
  requiring it, as server-side environment variables only.
- The policy was checked against the actual repository implementation: no
  material contradiction (the policy's permissive "may process / may
  include" language accommodates the current subset; Section 11's isolation
  claims are verified by Phase 2 tests).

### Alternatives

- Rendering the policy client-side from the markdown file at runtime:
  rejected — requires unnecessary JavaScript and a markdown parser.
- Adding META_* env vars now: rejected — speculative configuration.
- Inventing policy placeholders' values: forbidden.

### Consequences

The public privacy URL remains unavailable until deployment (R-007). The
policy page must be re-checked against the implementation whenever
data-handling behavior changes (later phases).

### Evidence

- Build: /privacy prerendered (7/7 static pages, exit 0).
- Live run: GET /privacy → HTTP 200 without authentication; heading,
  "Last Updated: September 29, 2026", 7 rendered placeholders, and all
  section markers present; footer link rendered on /login.
- tsc --noEmit + eslint: exit 0.
