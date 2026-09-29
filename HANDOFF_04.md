# HANDOFF — PHASE 04

## Phase

Phase 04 — WhatsApp Business Connection (autonomous run)

## Phase objective

Implement the Floww-side foundation for connecting a seller's WhatsApp
Business presence to Floww using Meta's current supported onboarding
architecture — with tenant ownership, secure credentials, and no fake
success. The seller must never provide Meta passwords or paste access
tokens into Floww UI.

## What was implemented

### Connection data model (migration 0003)
- `platform_connections`: uuid PK; tenant FK (CASCADE); platform
  (`whatsapp`); status (`initiated → connected → disconnected`); verified-
  shape identifiers (`waba_id`, `phone_number_id`); `account_identifiers`
  (JSONB — extension point for the verified evolving account model);
  `credentials_encrypted` (Fernet-encrypted); `connected_by_user_id` FK;
  lifecycle timestamps; DB CHECK constraints on status and platform.
- **Partial unique index** `uq_platform_connections_active` on
  (tenant_id, platform) WHERE status IN ('initiated','connected') — one
  ACTIVE connection per tenant+platform at the database level; disconnected
  rows are kept as history and excluded, so a tenant can reconnect (new
  row).

### Credential/secret abstraction
- `app/credential_store.py`: `CredentialStore` — Fernet (AES-128-CBC +
  HMAC-SHA256, `cryptography` package) encryption at rest; master key from
  `CREDENTIAL_ENCRYPTION_KEY` (server-side env, optional — the app starts
  without it; storing/reading credentials fails with a clear controlled
  error); tampered/wrong-key ciphertext → controlled error; `rotate_key`
  supported; plaintext never logged or returned.

### Meta adapter boundary (`app/meta/`)
- `MetaConnectionService` — ALL Meta-specific logic isolated here:
  - IMPLEMENTED (deterministic, verified): lifecycle state transitions
    (`initiate`/`connect`/`disconnect`), identifier normalization
    (identifiers stay strings — never int/precision loss), credential
    encryption via the store, credential destruction on disconnect.
  - NOT IMPLEMENTED — raise a controlled `MetaAuthorizationNotConfiguredError`
    instead of guessing undocumented behavior: `build_authorization_url`,
    `validate_authorization_callback`, `exchange_code_for_token`,
    `deauthorize`. `META_AUTHORIZATION_IMPLEMENTED = False` documents the
    state in code.

### Backend APIs (`app/routers/connections.py`)
- `GET /tenants/{id}/connection` — members view status (real DB state;
  `disconnected` when none). Never includes credential material.
- `POST /tenants/{id}/connection/initiate` — OWNER only; creates the
  `initiated` record; idempotent while initiated; 409 `conflict` when
  already connected; response states explicitly that Meta authorization is
  pending configuration (no fake Meta success).
- `DELETE /tenants/{id}/connection` — OWNER only; disconnects (history
  kept, credential material destroyed); 404 when nothing to disconnect.
- Consistent error envelope from Phase 1; structured audit events
  (`connection.initiated/connected/disconnected` — IDs only, no secrets).

### Frontend (Next.js)
- `lib/connections.ts` — typed client wired to the backend's actual
  contract (fetchConnection/initiateConnection/disconnectConnection).
- `/settings` page — Integrations card: WhatsApp connection status
  (Not Connected / Initiated / Connected), Connect WhatsApp action,
  Disconnect action, identifier display (WABA/phone number ID — not
  secrets), meaningful error states, sign-in gate for unauthenticated
  users; 401 handling (stale token → login redirect).
- Shell header now links to Settings (additive only).

### Privacy policy update (owner-provided facts only)
- `FLOWW_PRIVACY_POLICY.md` + the `/privacy` page: all 7
  `[TO BE COMPLETED]` placeholders replaced — Operator: Akshay K Prasad
  (an individual developer; Floww is NOT currently represented as a
  registered company or legal entity — no fictional entity/address/
  registration invented); Contact/Deletion email: akshaykprasad17@gmail.com
  (subject: "Floww Data Deletion Request"); Website:
  https://flow-psi-lac.vercel.app/. Zero placeholders remain.

## What was verified

| Check | Command / Method | Result |
|---|---|---|
| Backend full suite (Phase 1+2+3+4) | `cd backend && python -m pytest -q` | **137 passed, exit 0** (final run 101.38s) |
| Phase 4 adapter unit tests | `python -m pytest tests/test_meta_adapter.py` | 13 passed |
| Phase 4 connection API tests | `python -m pytest tests/test_connections.py` | 15 passed |
| Frontend tests | `cd frontend && npm test` | **30 passed (30), exit 0** (18 auth + 12 connection) |
| Frontend build | `npm run build` | ✓ Compiled, 8/8 pages (incl. `/privacy`, `/settings`), exit 0 |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Lint | `npm run lint` + `python -m ruff check .` | exit 0 (both) |
| git diff --check | `git diff --check` | exit 0 |
| Migration from clean DB | `db:fresh` + `alembic upgrade head` | 0001+0002+0003 applied, exit 0 |
| Live lifecycle | real server: initiate → idempotent → disconnect → reconnect | all verified (1. disconnected → 2. initiated+"pending configuration" → 3. idempotent 200 → 4. disconnected → 5. status disconnected → 6. reconnect 200) |
| Live tenant isolation | user B → A's connection (GET/initiate/DELETE) | 403/403/403 DENIED |
| Live credential security | connection API response scan | 0 credential-material matches; identifiers only |
| Live privacy page | `curl /privacy` | 4× operator, 6× email, 4× website, 0 placeholders |

## Meta documentation sources consulted

(each fetched exactly once per the network protocol, all HTTP 200)

1. https://developers.meta.com/resources/videos/unified-onboarding-whatsapp/
2. https://developers.meta.com/resources/videos/whatsapp-account-model-evolution/
3. https://developers.meta.com/resources/videos/whatsapp-usernames/

## Meta facts VERIFIED (official Meta resources, June 16, 2026)

- Embedded Signup v4 is the current unified onboarding architecture
  (WhatsApp, Messenger, Instagram Direct via one streamlined flow); a
  migration path from legacy v2/v3 exists.
- The account model is evolving: WABA is being split into WAAC (phone
  numbers) and PMA (templates and billing); a single phone number can be
  shared across multiple partners/integrations while billing stays separate;
  changes affect Embedded Signup and Cloud API calls.
- Usernames + Business Scoped User ID (BSUID) will replace phone numbers for
  users who adopt usernames; 30-day phone number visibility rule; contact
  book service / REQUEST_CONTACT_INFO button exist.

## Meta facts still UNKNOWN

- Exact Embedded Signup v4 session/configuration parameters
- Exact OAuth scopes/permissions for the authorization flow
- Exact token exchange endpoints and request/response shapes
- Exact authorization callback payload structures
- Current de-authorization endpoint/behavior
- Applicability of the Admin Verification path to this app's setup
- Exact webhook payload shapes (Phase 5 scope)

## Real API verification status

- REAL META API TEST = **BLOCKED** — required credentials unavailable in
  this environment; the owner's access token was never requested, printed,
  logged, or stored. All Meta-facing claims are labeled LOCAL ADAPTER TEST =
  PASS; no Meta connectivity is claimed.
- PUBLIC META CALLBACK = **BLOCKED** — the backend is not publicly deployed
  (the frontend is deployed at https://flow-psi-lac.vercel.app/; the backend
  callback infrastructure is not).

## Manual Meta actions

- Configure the Meta app's Privacy Policy URL to the public /privacy
  endpoint after deployment (R-007).
- Embedded Signup configuration (Facebook Login for Business settings,
  redirect URI registration) — only after the v4 specifics are verified
  against official documentation (R-008).
- Organization/Admin Verification path — determine applicability with the
  owner (no registered legal entity exists; none was invented).
- The owner's access token stays in the owner's Meta dashboard / secret
  storage — never in chat, Git, or documentation.

## Security considerations

- Tenant isolation: enforced server-side (membership checks + tenant-scoped
  queries); cross-tenant GET/POST/DELETE → 403; forged tenant IDs → 404;
  verified by tests AND a live run.
- Credential security: Fernet-encrypted at rest; plaintext never in DB,
  logs, responses, tests, or frontend; credential destruction on
  disconnect; tamper → controlled error; rotation supported; wrong/missing
  key → clear controlled failure.
- No client-supplied tenant ID is trusted; authorization resolves from
  `tenant_members`.
- Connection responses never include credential material or raw Meta
  payloads (verified: 0 credential matches in API responses).
- Logs carry IDs/status only — no tokens, authorization codes, or secrets
  (verified via log-capture tests).
- 401/403/404/409 distinguished consistently (Phase 1 envelope).
- Deferred: rate limiting, expired-session cleanup, cookie hardening
  (Phase 13); CORS allowlist already explicit.

## Database changes

- Migration `0003_platform_connections` (tables/constraints/indexes above);
  clean-database migration verified; rollback test-verified via the
  existing downgrade tests (to 0001/base).

## API changes

- New: `GET/DELETE /tenants/{id}/connection`,
  `POST /tenants/{id}/connection/initiate` (tenant-scoped, role-aware).
- New error codes: `credential_encryption_unavailable` (503),
  `credential_decrypt_failed` (503).

## Frontend changes

- New: `/settings` page (WhatsApp connection card), `lib/connections.ts`,
  `lib/connections.test.ts`.
- Modified: shell header (Settings link).

## Known limitations

- The Meta authorization flow (Embedded Signup v4) is NOT implemented — the
  detailed specifics could not be verified from this environment; the
  adapter refuses to guess (ADR-010). The "Connect WhatsApp" action records
  intent and clearly reports the pending configuration.
- Platform-side de-authorization is a manual action until the current
  endpoint is verified.
- The credential master key is environment-based (KMS/HSM is Phase 13
  hardening).
- No public backend callback (PUBLIC META CALLBACK = BLOCKED).
- A dedicated audit_logs table is deferred (structured logging is the
  current audit mechanism; table planned for Phase 8).

## Deferred work

- Embedded Signup v4 authorization flow (needs verified docs + owner
  dashboard configuration)
- Token exchange + callback handling (same)
- Platform-side de-authorization
- Webhook gateway (Phase 05)
- Message ingestion / normalization (Phase 06)
- Customer identity model with internal ID + platform identifiers
  (Phase 06; BSUID-aware per section 17)
- AI extraction (Phase 07); Instagram (Phase 09); billing (Phase 12);
  production deployment (Phase 14)

## Git

Commit: (phase-04 commit — see `git log` after checkpoint)
Tag: phase-04-complete

## Next phase

Phase 05 — Webhook Gateway (only after the Embedded Signup specifics are
verified and the manual Meta actions are completed).

Do not start the next phase until this handoff is reviewed.
