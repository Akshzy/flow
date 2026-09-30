# PHASE 05 — WEBHOOK GATEWAY

## Objective

Build a secure, idempotent, asynchronous inbound event gateway.

## Required flow

Provider
→ verification
→ tenant/connection resolution
→ validation
→ persistence
→ idempotency
→ queue
→ prompt response

## Tests

- valid verification
- invalid verification
- valid signature if applicable
- invalid signature
- malformed payload
- unknown event
- duplicate event
- retry/replay
- unknown connection
- revoked connection
- database failure
- queue failure
- timeout
- prompt HTTP response
- no slow AI work inside request

## Security

Test tenant resolution and event ownership.

## Completion

All mandatory gateway tests pass. Create handoff, evidence, commit/tag `phase-05-complete`, then STOP.

## Phase 05 implementation record (autonomous run)

- IMPLEMENTED: webhook gateway (`app/webhooks/` — auth, payload, service,
  router), SIMULATOR_ONLY HMAC authentication (raw bytes, constant-time,
  env-gated; disabled in production), payload contract + validation,
  request-size limit (413), connection/tenant resolution via server-
  controlled mappings (VERIFIED_META identifiers; CONNECTED only), database-
  level idempotency (unique dedup_key + IntegrityError backstop), raw event
  persistence (RECEIVED → PENDING_PROCESSING before ack; migration 0004),
  processing-state management + failure recording, restart-durability
  foundation (`pending_events` for Phase 6), deterministic simulator
  (`simulator/` — fixtures, client, scenarios, CLI) exercising the actual
  HTTP boundary.
- NOT IMPLEMENTED (UNKNOWN_META — blocked): Meta production webhook
  verification (hub.mode/hub.challenge/hub.verify_token) and signature
  scheme (X-Hub-Signature-256) — could not be verified from official docs in
  this environment; the production endpoint is explicitly blocked (503).
- VERIFIED (local): 165/165 backend tests (28 Phase 5: 21 webhook + 7
  simulator), 30/30 frontend, live run 18/18 scenarios (incl. concurrent
  race + persistence failure/recovery), DB inspection (6 events / 6 distinct
  dedup keys; all pending_processing; forged tenant ignored).
