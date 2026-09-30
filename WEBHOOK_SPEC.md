# WEBHOOK SPECIFICATION

## Implemented gateway (Phase 5)

Route: `POST /webhooks/whatsapp`

Flow (per the spec below — steps map to the implementation):

1. request-size limit (413 before the body is trusted)
2. SIMULATOR_ONLY authentication over the RAW request bytes (401)
3. payload parsing + validation — the SIMULATOR_ONLY contract (422)
4. connection + tenant resolution via server-controlled connection mappings
   (VERIFIED_META identifiers: `phone_number_id` / `waba_id`; only CONNECTED
   connections receive events) — 404 `unknown_connection`
5. database-level idempotency — unique `dedup_key`
   (`platform:connection_id:external_event_id`)
6. raw event persistence: `RECEIVED → PENDING_PROCESSING` in a single
   transaction, BEFORE the HTTP acknowledgement
7. prompt response — no Phase 06+ processing inside the request

### Status codes (SIMULATOR_ONLY contract, documented)

| Status | Code | Meaning |
|---|---|---|
| 202 | — | accepted: event durably persisted as `pending_processing` |
| 200 | — | duplicate: idempotent duplicate delivery (no second event; processing history untouched) |
| 401 | `unauthorized` | missing/invalid signature |
| 413 | `payload_too_large` | request body exceeds the documented size limit (default 1 MiB, `WEBHOOK_MAX_BODY_BYTES`) |
| 404 | `unknown_connection` | no connected connection matches the event identifiers |
| 422 | `validation_error` | malformed JSON / missing required fields / unsupported event type |
| 503 | `webhook_not_configured` | production: simulator auth disabled and the real Meta signature scheme is not implemented (blocked) |
| 500 | `internal_error` | persistence failure — never acknowledged as accepted/duplicate |

## REAL META BOUNDARY — BLOCKED (UNKNOWN_META)

Meta's production webhook verification (`hub.mode` / `hub.challenge` /
`hub.verify_token`) and signature scheme (`X-Hub-Signature-256`) could not be
verified from official documentation in this environment (the docs pages are
client-rendered; see INTEGRATIONS.md). Therefore:

- the production Meta verification endpoint is NOT implemented;
- the production Meta signature verification is NOT implemented;
- the SIMULATOR_ONLY HMAC mechanism (`X-Floww-Simulator-Signature`,
  HMAC-SHA256 over raw bytes, constant-time comparison) is a Floww-defined
  contract for deterministic local testing — it is NEVER Meta's production
  signature scheme;
- the webhook endpoint is explicitly blocked in production (503
  `webhook_not_configured`) — no unauthenticated production endpoint exists.

Before production Meta webhooks (a later phase): verify the current official
Meta webhook documentation (verification handshake, signature scheme, payload
structure, subscription requirements), then implement the verified boundary.

## Required behavior (original spec — retained for the production boundary)

A webhook endpoint must:

1. accept the provider's documented request format
2. perform required verification
3. validate signatures/tokens where documented
4. resolve the correct platform connection/tenant
5. persist the event
6. enforce idempotency
7. enqueue asynchronous processing
8. return the documented success response promptly

## Failure cases (tested)

- invalid verification (production blocked — 503)
- invalid signature (401)
- malformed payload (422)
- unknown event type (422)
- duplicate event (200, idempotent — sequential, repeated and concurrent)
- unknown tenant/connection (404)
- revoked connection (only CONNECTED connections receive events; an
  `initiated` connection is not authorized)
- database failure (500; never falsely acknowledged)
- timeout (bounded: 5s DB connect timeout; the request never hangs)
- provider retry (idempotent duplicate handling)

## Security

- Tenant resolution is server-side only: the tenant derives from the resolved
  connection (via VERIFIED_META identifiers mapped in
  `platform_connections`); a `tenant_id` inside an external payload is never
  trusted (tested: forged tenant ids are ignored).
- Authenticate before trusting payload contents.
- Request-size limit enforced (413).
- Constant-time comparison for authentication values.
- Raw message bodies are never logged (only event ids, tenant ids, event
  types, statuses).
- Simulator-only capabilities are gated by environment (disabled in
  production).
