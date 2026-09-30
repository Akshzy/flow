# HANDOFF — PHASE 05

## Phase

Phase 05 — Deterministic Simulator + Webhook Gateway (autonomous run)

## Status

COMPLETE (local implementation + verification, including live end-to-end);
the production Meta webhook boundary is UNKNOWN_META and explicitly blocked.

## 1. Implemented components

- **Webhook gateway** (`app/webhooks/`):
  - `auth.py` — SIMULATOR_ONLY HMAC-SHA256 authentication over the RAW
    request bytes (header `X-Floww-Simulator-Signature`, constant-time
    comparison via `hmac.compare_digest`, server-controlled
    `SIMULATOR_SIGNING_SECRET`, ENABLED only outside production).
  - `payload.py` — the SIMULATOR_ONLY payload contract
    (`SimulatorEventPayload`: type/phone_number_id/from/message_id required;
    waba_id/text/timestamp optional), validation (`parse_payload` →
    `PayloadValidationError`), and `dedup_key_for`
    (`platform:connection_id:external_event_id`).
  - `service.py` — connection/tenant resolution via server-controlled
    connection mappings (VERIFIED_META identifiers; CONNECTED connections
    only), idempotency (fast-path check + unique-constraint backstop), event
    persistence (RECEIVED → PENDING_PROCESSING in one transaction, BEFORE
    the ack), processing-failure recording (`FAILED`), and
    `pending_events` (the Phase 6 consumption entry point).
  - `router.py` — `POST /webhooks/whatsapp`: size limit (413) → auth (401)
    → validation (422) → resolution (404) → idempotency/persistence (500
    backstop) → acknowledgement (202 accepted / 200 duplicate).
- **Deterministic simulator** (`simulator/`):
  - `fixtures.py` — stable identifiers (fake senders, fixture connection
    ids, stable message ids), deterministic payload builders, HMAC signing,
    deterministic serialization (sorted keys).
  - `client.py` — `SimulatorClient`: signs the raw bytes and submits over
    HTTP (never bypasses the gateway; never writes to the DB);
    `override_signature`/`omit_signature` for failure scenarios.
  - `scenarios.py` — the deterministic scenario set (18 recorded outcomes
    incl. the persistence-failure hook scenarios).
  - `setup.py` — TEST-ONLY fixture mechanism (idempotent creation of the
    connected fixture connection via the DB layer; NOT a production API).
  - `__main__.py` — CLI: `python -m simulator setup --database-url ...` and
    `python -m simulator run --base-url ... --secret ... [--database-url ...]`
    (the last enables the persistence-failure scenario).

## 2. Actual architecture

See ARCHITECTURE.md ("Webhook gateway (Phase 5)") — the simulator submits
over HTTP only; the gateway authenticates → validates → resolves →
deduplicates → persists → acknowledges. Phase 06 processing is NOT executed
inside the request.

## 3. Simulator contract (SIMULATOR_ONLY)

- Payload: `{"type": "messages", "phone_number_id": "...", "from": "...",
  "message_id": "...", "waba_id": "...?", "text": {...}?, "timestamp": ...?}`
  — synthetic identifiers/customer data only.
- Authentication: HMAC-SHA256 hex digest over the raw serialized bytes with
  the server secret (deterministic; `serialize` uses sorted keys).
- Floww-defined for deterministic local testing — NEVER Meta's production
  signature scheme.

## 4. Verified Meta facts (VERIFIED_META)

- phone_number_id and WABA identifiers exist and identify WhatsApp business
  assets (official Meta resources, June 2026 — see INTEGRATIONS.md).
- Embedded Signup v4 (unified onboarding), the WAAC/PMA account-model split,
  and Usernames/BSUID with the 30-day phone visibility rule (Phase 4
  research, verified June 2026).

## 5. Unknown Meta facts (UNKNOWN_META)

- The webhook verification handshake (hub.mode/hub.challenge/hub.verify_token)
- The signature scheme (X-Hub-Signature-256) — the production webhook
  boundary is NOT implemented and is blocked in production (503
  `webhook_not_configured`)
- The production webhook payload structure and event identifiers
- Subscription requirements

## 6. Event schema and lifecycle

- Schema: see DATA_MODEL.md ("webhook_events (Phase 5)") — migration 0004.
- Lifecycle: `RECEIVED` (transient, in-transaction) → `PENDING_PROCESSING`
  (durably persisted before the HTTP ack) → `FAILED` (processing failures,
  inspectable — Phase 6 worker). Documented in DATA_MODEL.md and
  `app/models.py` (`ProcessingState`).

## 7. Authentication mechanism

SIMULATOR_ONLY HMAC over raw bytes (constant-time, env-gated, disabled in
production). Production Meta verification: NOT implemented (UNKNOWN_META) —
the endpoint is explicitly blocked in production.

## 8. Tenant-resolution mechanism

Server-controlled connection mappings only: the event's identifiers
(phone_number_id/waba_id) are matched against CONNECTED rows in
`platform_connections`; the tenant derives from the resolved connection. A
`tenant_id` inside a payload is never trusted (test-verified: forged ids are
ignored and the event lands under the connection's tenant).

## 9. Idempotency strategy

Database-level unique `dedup_key`
(`platform:connection_id:external_event_id`) — the application-level check
is the fast path; the unique constraint is the concurrency backstop
(IntegrityError → mapped to the duplicate result). Duplicate responses are
deterministic (200 + the existing event id + processing state) and never
reset processing history. Exactly-once HTTP delivery is NOT claimed.

## 10. Test results

| Suite | Command | Result |
|---|---|---|
| Backend full (Phases 1-5) | `cd backend && python -m pytest -q` | **165 passed, exit 0** (96.20s) |
| Phase 5 webhook API tests | `python -m pytest tests/test_webhook.py` | 21 passed |
| Phase 5 simulator tests | `python -m pytest tests/test_simulator.py` | 7 passed |
| Frontend tests | `cd frontend && npm test` | **30 passed (30), exit 0** |
| Frontend build | `npm run build` | ✓ 8/8 pages, exit 0 |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Lint | `npm run lint` / `python -m ruff check .` | exit 0 (both) |
| Migrations from clean DB | `db:fresh` + `alembic upgrade head` | 0001-0004 applied, exit 0 |

## 11. Live verification evidence

Ran the real FastAPI app (uvicorn) + the real embedded PostgreSQL; executed
the simulator CLI over HTTP (`python -m simulator run --secret ...`):

```text
SCENARIO                     EXPECTED                                           HTTP   RESULT
valid_text                   202 accepted                                       202    PASS
same_sender_second           202 accepted                                       202    PASS
different_sender             202 accepted                                       202    PASS
exact_duplicate              200 duplicate                                      200    PASS
repeated_duplicate_1-3       200 duplicate                                      200    PASS (x3)
malformed_json               422 validation_error                               422    PASS
missing_fields               422 validation_error                               422    PASS
invalid_auth                 401 unauthorized                                   401    PASS
modified_after_signing       401 unauthorized                                   401    PASS
unknown_connection           404 unknown_connection                             404    PASS
cross_tenant_injection       202 accepted (forged tenant ignored)               202    PASS
unsupported_event            422 validation_error                               422    PASS
oversized_payload            413 payload_too_large                               413    PASS
concurrent_duplicates        exactly one 202; the rest 200 duplicate            [200,202,200,200,200] PASS
persistence_failure          500 internal_error; no accepted/duplicate ack      500    PASS
persistence_recovery         202 accepted                                       202    PASS
18/18 scenarios passed
```

Database inspection (after the run): **6 events / 6 DISTINCT dedup keys**
(despite 9 duplicate deliveries + 5 concurrent submissions); all 6 in
`pending_processing`; duplicate-id counts = 1 each; every event's tenant
matches its connection; the forged-tenant event landed under the fixture
tenant (the forged id was ignored).

Restart durability (live): after a real app restart, the pre-restart event
remains durably available (`pending_processing`) and a duplicate submission
returns the deterministic duplicate response referencing the same event id.

## 12. Known limitations

- The production Meta webhook boundary is NOT implemented (UNKNOWN_META) —
  the endpoint is blocked in production (503). Verify current official Meta
  docs before implementing it.
- The simulator contract is SIMULATOR_ONLY — it does not prove Meta
  production behavior.
- The event lifecycle stops at PENDING_PROCESSING — no queue/worker exists
  (Phase 6).
- The persistence-failure scenario uses a TEST-ONLY table rename (fully
  recovered) via the CLI hook.
- The simulator's stable-fixture scenarios assume a fresh database (or
  expect duplicates for previously-seen fixture ids — the system's
  idempotency working as designed).
- The TEST-ONLY fixture mechanism (connected connection) is a documented
  test-entry device; no production API marks connections as authorized.

## 13. Deferred work

- Phase 06: message normalization, customer resolution (internal ID +
  platform identifiers; BSUID-aware), conversations/messages persistence,
  consuming `pending_events`.
- Production Meta webhook verification/signatures (after verifying current
  official docs).
- Queue/worker infrastructure (Phase 6 decision).
- Phase 07/08/09+ (AI extraction, orders, Instagram); Phase 13 hardening
  (rate limiting, KMS, cookie hardening); Phase 14 (deployment).

## 14. Git checkpoint

Commit: (phase-05 commit — see `git log` after checkpoint)
Tag: phase-05-complete

## 15. Exact Phase 06 entry requirements

- Consume events via `app.webhooks.service.pending_events(db)` — durable,
  ordered by receipt, `PENDING_PROCESSING` only.
- The raw payload (`webhook_events.raw_payload`, JSONB) is the source for
  normalization; `tenant_id`/`connection_id` are pre-resolved (trusted,
  server-controlled).
- Record failures via `app.webhooks.service.record_processing_failure`
  (sets `FAILED`, increments attempts); mark processed via
  `processed_at` + the phase-6 processing state extensions.
- The payload contract (SIMULATOR_ONLY) must be reconciled with the
  verified Meta webhook payload shape before production ingestion.
- Duplicate deliveries after processing must NOT reset a completed event
  (the gateway returns the duplicate response and never overwrites
  processing history).
