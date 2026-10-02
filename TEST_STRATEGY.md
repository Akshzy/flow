# TEST STRATEGY

## Test pyramid

### Unit

Pure business logic and transformations.

### Integration

Database, queues, internal services, provider adapters.

### API/contract

HTTP requests, schemas, authentication, error handling.

### Security

Authentication, authorization, tenant isolation, secret handling, webhook verification.

### End-to-end

Realistic seller → platform → webhook → processing → order flow where technically possible.

### External verification

Tests against provider sandbox/test assets where available.

A local mock is NOT external verification.

## Required negative testing

Every phase must test relevant failure paths.

Minimum categories:

- invalid input
- missing input
- unauthorized access
- forbidden access
- duplicate request/event
- dependency failure
- timeout
- malformed payload
- invalid state transition
- unexpected provider response

## Completion rule

A phase cannot pass if a mandatory test fails.

If a test cannot reasonably be executed, document why and classify the verification state explicitly.

## Phase 05 additions (webhook gateway + simulator)

- Simulator scenarios exercise the ACTUAL HTTP webhook boundary (ASGI stack
  in tests; a real server in live verification) — they never bypass the
  gateway or write into the event database.
- Concurrency: concurrent duplicate submissions via asyncio.gather — the DB
  unique constraint is the backstop (exactly one event survives).
- Persistence failure: monkeypatched persistence (deterministic) — the
  gateway must never acknowledge a failed write as accepted/duplicate.
- Restart durability: a new app instance against the same database —
  accepted events remain durably available; duplicates stay deterministic.

## Phase 08 additions (order management)

- The state machine is verified by valid AND invalid transition tests
  (invalid transitions must never silently succeed).
- Transaction rollback: forced mid-transaction failures must leave no orphan
  orders/items and no falsely completed extraction state.
- Idempotency: repeated and concurrent candidate conversion → one order.
- Tenant isolation: cross-tenant GET/confirm/cancel → 403; forged tenant ids
  → 404 (no existence inference).
- Repeated testing: transaction/concurrency/rollback tests are run 3+
  consecutive times (deterministic behavior required).
