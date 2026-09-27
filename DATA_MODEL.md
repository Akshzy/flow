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
