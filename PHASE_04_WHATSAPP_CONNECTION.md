# PHASE 04 — WHATSAPP CONNECTION

## Objective

Implement the official WhatsApp connection/onboarding flow for a seller.

## Required work

Implement only the currently documented Meta flow verified in Phase 00/03 and re-verified now.

The system must:
- initiate connection
- validate callback/state
- associate connection with correct tenant
- store required connection metadata securely
- show connection status
- support disconnect/reconnect where supported

## Tests

- successful authorization
- user cancellation
- authorization denial
- invalid state
- expired state
- duplicate connection
- reconnect
- disconnect
- tenant isolation
- credential/logging security

## External verification

Where possible, perform a real Meta test with a development/test asset.

Clearly label:
VERIFIED / PARTIALLY VERIFIED / NOT VERIFIED.

## Completion

Do not fake a Meta result. Create handoff, evidence, commit/tag `phase-04-complete`, then STOP.

## Phase 04 implementation record (autonomous run)

- IMPLEMENTED: connection data model (`platform_connections`, migration
  0003, partial unique index = one active connection per tenant+platform),
  tenant ownership + isolation (server-side membership checks), Meta
  adapter boundary (`app/meta/adapter.py`) with verified lifecycle state
  transitions and identifier normalization, encrypted credential store
  (Fernet, key from `CREDENTIAL_ENCRYPTION_KEY`), connection APIs (status /
  initiate / disconnect — OWNER-only actions), structured-logging audit
  events (no secrets), Settings/Integrations UI with connection status and
  actions, frontend connection client + tests.
- NOT IMPLEMENTED (unverified current Meta behavior — adapter refuses to
  guess, see ADR-010): Embedded Signup v4 authorization URL, callback
  validation, token exchange, platform-side de-authorization. Recorded as
  MANUAL ACTION REQUIRED / DEFERRED in HANDOFF_04.md.
- VERIFIED (local): 28/28 Phase 4 backend tests (13 adapter + 15 API),
  live lifecycle run (initiate → idempotent → disconnect → reconnect),
  live tenant isolation (cross-tenant 403), credential-free responses.
- NOT VERIFIED: REAL META API TEST = BLOCKED (credentials unavailable;
  never requested).
