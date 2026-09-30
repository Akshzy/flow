# DATA MODEL

Initial entities:

- users
- tenants
- tenant_members
- platform_connections
- webhook_events
- conversations
- messages
- customers
- orders
- order_items
- ai_extractions
- audit_logs

## Implemented so far

- `users`, `tenants`, `tenant_members` (Phase 2), `auth_sessions` (Phase 2)
- `platform_connections` (Phase 4)
- `webhook_events` (Phase 5)
- `app_meta` (Phase 1 foundation)

`conversations`, `messages`, `customers`, `orders`, `order_items`,
`ai_extractions` and `audit_logs` arrive in the phases that require them
(Phase 6+). No customer/conversation/message/order tables exist yet.

## webhook_events (Phase 5)

- `id` — internal event ID (uuid)
- `dedup_key` (UNIQUE) — database-level idempotency; scope:
  `platform:connection_id:external_event_id` (tenant-scoped through the
  resolved connection)
- `external_event_id` — the provider's event identifier
- `platform`, `event_type` — e.g. whatsapp / messages
- `connection_id` — the resolved (CONNECTED) platform connection
- `tenant_id` — resolved via the connection (never from payload fields)
- `raw_payload` (JSONB) — the raw event as received, retained for Phase 6;
  never logged
- `received_at`, `external_timestamp` — receipt + provider timestamp
- `processing_state` — lifecycle below
- `processing_attempts`, `last_processing_error`, `processed_at` —
  processing history (Phase 6 worker consumes)

## Event lifecycle (Phase 5)

```text
RECEIVED (transient, in-transaction)
   ↓
PENDING_PROCESSING (durably persisted before the HTTP ack)
   ↓ (Phase 6 processing; failures recorded as)
FAILED (inspectable; processing_attempts/last_processing_error updated)
```

Accepted events remain durably available after an application restart;
duplicate deliveries never reset a persisted event or overwrite its
processing history.

## Ownership

Every tenant-owned entity must have an explicit tenant relationship or a provable ownership chain.

## Order states

```text
NEW
  ↓
NEEDS_REVIEW
  ↓
CONFIRMED
  ↓
PROCESSING
  ↓
COMPLETED
```

Additional terminal/error states:

```text
CANCELLED
FAILED
```

State transitions must be enforced by application logic and tested.

## Idempotency

External event IDs and other appropriate idempotency keys must prevent duplicate processing.

## Sensitive information

Customer contact and address data are sensitive application data.

Access, logging, exports, and retention must be deliberate.
