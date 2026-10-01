# ARCHITECTURE

## High-level

Seller Web App
→ API
→ Authentication/Tenant Layer
→ Application Services
→ PostgreSQL

External platforms
→ Webhook Gateway
→ Event Store
→ Queue/Worker
→ Message Normalizer
→ AI Extraction
→ Deterministic Validation
→ Order Service
→ Seller Review
→ Export

## Public pages

- `/privacy` — public-facing Privacy Policy (source of truth:
  `FLOWW_PRIVACY_POLICY.md`; rendered server-side, no authentication,
  linked from the app footer). Meta app review requires this URL to be
  publicly accessible after deployment.

## Webhook gateway (Phase 5)

```text
Deterministic simulator (HTTP only, never DB writes)
        ↓
POST /webhooks/whatsapp
        ↓
Request-size limit (413)
        ↓
SIMULATOR_ONLY HMAC auth over raw bytes (401; disabled in production)
        ↓
Payload parsing + validation — SIMULATOR_ONLY contract (422)
        ↓
Connection/tenant resolution — server-controlled connection mappings,
VERIFIED_META identifiers (phone_number_id / waba_id); only CONNECTED
connections receive events (404 unknown_connection); the tenant NEVER
comes from payload fields
        ↓
Database-level idempotency — unique dedup_key (IntegrityError backstop)
        ↓
Raw event persistence — RECEIVED → PENDING_PROCESSING in one transaction,
BEFORE the acknowledgement
        ↓
Prompt HTTP response (202 accepted / 200 duplicate)
```

Components: `app/webhooks/` (auth, payload, service, router) and
`simulator/` (fixtures, client, scenarios, CLI). The real Meta webhook
boundary (hub verification + signature scheme) is UNKNOWN_META and blocked —
see WEBHOOK_SPEC.md and INTEGRATIONS.md.

Phase 06 consumes pending events via
`app.webhooks.service.pending_events` (durably available after restart).

## Message pipeline (Phase 6)

```text
PENDING_PROCESSING events (app.webhooks.service.pending_events)
        ↓
Deterministic consumer (app.pipeline.consumer; CLI: python -m app.pipeline process)
        ↓
Normalization (app.pipeline.normalization — no LLM, no fuzzy matching)
        ↓
Customer resolution — internal Floww ID + platform identity mapping
(UNIQUE per tenant/platform/external_user_id + SAVEPOINT create-or-reuse)
        ↓
Conversation resolution — one OPEN conversation per
(tenant, customer, connection) via partial unique index
        ↓
Message persistence — UNIQUE source_event_id (one message per event)
        ↓
Event marked PROCESSED in the SAME transaction (all-or-rollback)
```

Identity is based on explicit platform identifiers only — never names,
text similarity, typing style, or metadata. Failures roll the transaction
back, increment processing_attempts, record last_processing_error, set the
event to FAILED (inspectable), and remain bounded-retryable
(MAX_PROCESSING_ATTEMPTS = 5; no loops).

## Recommended stack

Frontend:
- Next.js
- TypeScript
- Tailwind

Backend:
- FastAPI
- Python

Data:
- PostgreSQL
- Redis/queue

Storage:
- S3-compatible object storage when required

AI:
- structured-output capable model

## Design rule

External platform adapters must be isolated from core order logic.

The core application should consume normalized internal events/messages instead of depending on one vendor's payload structure.

## Webhook rule

Webhook handlers should:

1. authenticate/verify the request
2. identify the tenant/platform connection
3. validate basic structure
4. persist the raw event safely
5. enforce idempotency
6. enqueue work
7. return promptly

Slow AI processing must not block the webhook request.
