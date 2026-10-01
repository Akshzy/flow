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
- `customers`, `customer_platform_identities`, `conversations`, `messages`
  (Phase 6)
- `app_meta` (Phase 1 foundation)

`orders`, `order_items`, `ai_extractions` and `audit_logs` arrive in the
phases that require them (Phase 7+). No order/AI tables exist yet.

## Phase 6 pipeline entities

- `customers` — the internal Floww customer identity (tenant-owned). The
  internal Floww ID is the customer identity; platform-specific identity
  lives in `customer_platform_identities`. The phone number is NOT the
  immutable primary key (BSUID/usernames will replace it for username
  adopters per the verified Meta account-model evolution).
- `customer_platform_identities` — customer ↔ platform identity mapping;
  UNIQUE (tenant, platform, external_user_id) — database-level protection
  against concurrent duplicate customers.
- `conversations` — one OPEN conversation per (tenant, customer, connection)
  via a partial unique index; resolution is deterministic (never text- or
  similarity-based).
- `messages` — one message per source event (UNIQUE `source_event_id`);
  retains the trace chain tenant → conversation → customer → source event;
  `message_type` ("text" supported), `body`, `external_timestamp`.

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
   ↓ (Phase 6 consumer: normalize → customer → conversation → message,
           one transaction; success marks)
PROCESSED (processed_at set; downstream records durable)
   ↓ (a failed attempt records)
FAILED (inspectable; processing_attempts/last_processing_error updated;
        bounded retry via the processor's --retry-failed, max 5 attempts)
```

Accepted events remain durably available after an application restart;
duplicate deliveries never reset a persisted event or overwrite its
processing history. The pipeline's transaction boundary is all-or-nothing:
the event is marked PROCESSED only when customer/conversation/message are
durable in the same transaction.

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
