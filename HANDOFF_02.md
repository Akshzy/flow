# HANDOFF — PHASE 02

## Phase

Phase 02 — Authentication and Multi-Tenancy

## Status

COMPLETE

## Implemented

Building on the Phase 1 foundation (app factory, lifespan, error envelope,
request IDs, structured logging, PostgreSQL + Alembic, test infrastructure):

### Authentication
- **Registration** (`POST /auth/register`): email (syntax-validated via
  pydantic `EmailStr`, lowercased) + password (min 8 chars); duplicate email →
  409 `conflict`; invalid input → 422 envelope with whitelisted details (raw
  input values never echoed).
- **Passwords**: argon2id hashes only (argon2-cffi, OWASP-recommended, library
  defaults); never stored or logged in plaintext; no custom cryptography.
- **Login** (`POST /auth/login`): verifies the argon2id hash; unknown email and
  wrong password return the IDENTICAL generic 401 `invalid_credentials` (no
  account enumeration); returns an opaque bearer token.
- **Sessions/tokens**: server-side sessions in `auth_sessions` — random
  `secrets.token_urlsafe(32)` tokens, only the SHA-256 hash persisted, TTL
  from `SESSION_TTL_HOURS` (default 168h); expiry enforced at lookup →
  401 `session_expired` (distinct from `unauthorized`).
- **Session validation** (`GET /auth/me`): bearer-token lookup + expiry +
  user resolution; missing/invalid/malformed credentials → 401.
- **Logout** (`POST /auth/logout`): deletes the session row server-side; the
  token becomes unusable immediately; other sessions are unaffected.

### Users / tenants / memberships
- `users` (uuid PK, unique email, argon2id `password_hash`, status,
  timestamps), `tenants` (uuid PK, name, status, timestamps),
  `tenant_members` (uuid PK, FKs with ON DELETE CASCADE, unique
  (tenant_id, user_id), role `owner|member` with a DB CHECK constraint,
  timestamps), `auth_sessions` (token_hash PK, user FK, expiry, indexes).

### Authorization (separate from authentication)
- `get_current_user` (authentication) and `require_membership(role)`
  (authorization) are distinct dependencies; every tenant route enforces
  membership server-side — a client-supplied tenant ID is never proof of
  access.
- `GET /tenants` is tenant-scoped (membership join filtered by user_id —
  never the full table).
- `PATCH`/`DELETE /tenants/{id}` require the OWNER role (403 for plain
  members and non-members).
- Status code contract: 401 `unauthorized`/`invalid_credentials`/
  `session_expired`, 403 `forbidden`, 404 `not_found`, 409 `conflict`,
  422 `validation_error`.

### Tenant isolation
- The tenant object itself is the Phase 2 protected resource (ADR-008); no
  future-phase placeholder resources were created.
- Enforced in the backend/data-access layer (membership checks +
  tenant-scoped queries), verified by cross-tenant and IDOR tests and a live
  run.

### Frontend (Next.js 15 + TypeScript + Tailwind)
- `lib/auth.ts`: token + selected-tenant persistence (localStorage), typed
  `apiFetch` returning `{ok,status,data|error}`, register/login/logout/
  fetchMe/fetchTenants/createTenant — wired to the backend's ACTUAL contract.
- `/register`: email+password form; validation/duplicate/API-unreachable
  errors; success auto-signs-in and continues into the authenticated state.
- `/login`: email+password form; safe generic error on 401.
- `/` (authenticated shell): loading state; unauthenticated users see only
  sign-in/register links (protected UI hidden); authenticated users see their
  email, sign-out, tenant list with backend-provided roles, tenant creation,
  and tenant selection (persisted, restored on reload if still valid).
- No middleware (not required — gating is client-side, enforcement is
  backend-side); no refresh tokens/OAuth/MFA/password-reset/email
  verification (not in Phase 2 scope).

## Tests

| Suite | Command | Result |
|---|---|---|
| Backend (full: unit + API + integration + migration + failure) | `cd backend && python -m pytest` | **109 passed in 99.52s, exit 0** |
| Backend auth (registration/login/sessions/logout) | `python -m pytest tests/test_auth.py` | 20 passed |
| Backend tenants (CRUD/roles) | `python -m pytest tests/test_tenants.py` | 21 passed |
| Backend tenant isolation | `python -m pytest tests/test_isolation.py` | 17 passed |
| Backend security primitives | `python -m pytest tests/test_security.py` | 6 passed |
| Backend migrations (incl. Phase 2 tables + rollback) | `python -m pytest tests/test_migrations.py` | 7 passed |
| Frontend auth client | `cd frontend && npm run test` | **18 passed (18), exit 0** |
| Backend lint/format/type | `python -m ruff check .` / `ruff format --check .` / `python -m mypy app` | all exit 0 |
| Frontend type/lint/build | `npm run typecheck` / `npm run lint` / `npm run build` | all exit 0 |

Phase 1 regression: the original 40 Phase 1 tests are included in the 109 and
all pass (`test_config` 9, `test_logging` 7, `test_health` 8, `test_errors` 7,
`test_db` 4, `test_migrations` 7 incl. the original clean-database and
repeat-migration tests).

## Security Verification

Exact checks performed (VERIFIED unless noted):

- **Password storage**: argon2id only — DB-level check proves the stored hash
  starts with `$argon2id$` and the plaintext never appears (test + live).
- **Token/session handling**: only SHA-256 token hashes persisted (unit
  tests: `hash_token` deterministic, ≠ token); expiry enforced (expired
  session → 401 `session_expired`); login response contains the token (by
  design); `/auth/me` does not.
- **Logout invalidation**: token unusable after logout; other sessions
  survive; double-logout fails safely (401).
- **Authentication bypass**: every protected route goes through
  `get_current_user`; missing/invalid/malformed Authorization headers → 401
  (parametrized tests incl. `Basic` scheme).
- **Authorization bypass / IDOR / tenant isolation**: cross-tenant
  GET/PATCH/DELETE → 403; forged/random UUID → 404; blocked rename does not
  change the victim tenant; list endpoints return only the caller's tenants;
  data-layer membership queries are user-scoped (IDOR predicate tests); DB
  CHECK rejects role values outside owner/member.
- **Mass assignment**: request models declare explicit fields; unknown fields
  are ignored and roles are assigned server-side (tested).
- **User enumeration**: identical 401 for unknown email vs wrong password
  (response bodies compared, excluding the intentionally-unique request_id);
  registration returns 409 for duplicates (deliberate, standard tradeoff).
- **Sensitive error leakage**: error envelope contains code/message only; no
  password hashes, stack traces, or DB details (Phase 1 handler tests cover
  the 500 path; Phase 2 tests cover 401/403/404/409).
- **Logging**: logs contain user_id/tenant_id/status/duration only — no
  passwords, tokens, or credentials (source review + `test_login_never_logs_password`).
- **CORS**: explicit origins from `CORS_ORIGINS` (no wildcard),
  `allow_credentials=False`, explicit method/header allowlists.
- **Cookies/CSRF**: cookies are not used (bearer tokens) — CSRF is not
  applicable to this design; cookie hardening is Phase 13 work if cookies are
  introduced.
- **Client-supplied tenant IDs**: never trusted; authorization is resolved
  from `tenant_members` only.

PARTIALLY VERIFIED / deferred: rate limiting (Phase 13), expired-session row
cleanup (Phase 13), production CORS origin list (deployment configuration).

## Database

- Migration `0002` (users, tenants, tenant_members, auth_sessions) on top of
  Phase 1's `0001` (app_meta).
- Clean-database verification: fresh cluster (`npm run db:fresh`) →
  `python -m alembic upgrade head` → 0001 + 0002 applied, exit 0; repeated
  run exit 0 (no-op).
- Constraint verification: `uq_users_email` UNIQUE,
  `ck_tenant_members_role` CHECK(owner/member), cascade FKs.
- Rollback: `downgrade` to 0001 removes the Phase 2 tables and keeps
  `app_meta` (test-verified); `downgrade` to base removes everything (test-
  verified; alembic keeps the empty `alembic_version` table — standard
  alembic behavior).
- Live run against the running app: register/login/tenants all persisted to
  PostgreSQL; `application.database_connected` logged.

## Known Limitations

- Session tokens are stored in browser localStorage (XSS-exposed surface;
  standard React escaping applies). Cookie-based sessions + CSRF protection
  are Phase 13 hardening work (R-006).
- Expired session rows are not removed on access (periodic cleanup deferred
  to Phase 13).
- No rate limiting on auth endpoints (Phase 13).
- No password reset / email verification / MFA (not in Phase 2 scope).
- Tenant membership creation beyond the OWNER-on-create flow has no API yet
  (invite flow is future-phase scope); the membership table and role model
  are in place.
- The CI workflow has not been executed on GitHub Actions (no runner locally).

## UNKNOWN items

- CI execution on GitHub Actions: UNKNOWN until first push/run.
- Production hosting/CORS origins/deployment: UNKNOWN (Phases 13/14).
- External integrations (Meta/WhatsApp/Instagram/AI): NOT IMPLEMENTED,
  NOT VERIFIED — future phases.

## Files changed

```text
backend/.env.example                                   modified (+SESSION_TTL_HOURS, +CORS_ORIGINS)
backend/app/config.py                                  modified (+2 settings)
backend/app/db.py                                      modified (+create_session_factory)
backend/app/main.py                                    modified (+routers, +CORS, +session_factory)
backend/app/models.py                                  modified (+User/Tenant/TenantMember/AuthSession)
backend/pyproject.toml                                 modified (+argon2-cffi, +email-validator)
backend/tests/conftest.py                              modified (client uses migrated DB)
backend/tests/test_migrations.py                       modified (+Phase 2 migration/rollback tests)
backend/app/deps.py                                    new (auth + authorization dependencies)
backend/app/routers/__init__.py                        new
backend/app/routers/auth.py                            new (register/login/me/logout)
backend/app/routers/tenants.py                         new (tenant-scoped CRUD, OWNER role)
backend/app/schemas.py                                 new (request/response models)
backend/app/security.py                                new (argon2id + token hashing)
backend/migrations/versions/0002_users_tenants_memberships.py  new
backend/tests/helpers.py                               new
backend/tests/test_auth.py                             new (20 tests)
backend/tests/test_isolation.py                        new (17 tests)
backend/tests/test_security.py                         new (6 tests)
backend/tests/test_tenants.py                          new (21 tests)
frontend/lib/auth.ts                                   new (client auth helpers)
frontend/lib/auth.test.ts                              new (18 tests)
frontend/app/page.tsx                                  modified (authenticated shell + tenant UI)
frontend/app/login/page.tsx                            new
frontend/app/register/page.tsx                         new
frontend/package.json                                  modified (+test scripts, vitest, happy-dom)
frontend/package-lock.json                             modified (generated)
frontend/vitest.config.mjs                             new
DECISIONS.md                                           modified (+ADR-007, ADR-008)
RISKS.md                                               modified (+R-006, R-002 mitigated)
PROJECT_STATUS.md                                      modified (Phase 02 status)
HANDOFF_02.md                                          new
```

## Git

Commit: (phase-02 commit — see `git log` after checkpoint)
Tag: phase-02-complete

## Remote push verification

Phase 1 checkpoint pushed and verified before Phase 2 began:
origin/main and origin/phase-01-complete both at `ab14529` (verified via
`git ls-remote origin` / `git ls-remote --tags origin`). The Phase 2 commit
and tag are pushed after the local checkpoint; verification recorded below
in PROJECT_STATUS.md and the final report.

## Next Phase

Phase 03 — Meta Developer Infrastructure

Do not start the next phase until this handoff is reviewed.
