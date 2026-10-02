# PHASE 08 — ORDER MANAGEMENT

## Objective

Create the authoritative order lifecycle and seller review workflow.

## Required states

NEW
NEEDS_REVIEW
CONFIRMED
PROCESSING
COMPLETED
CANCELLED
FAILED

## Required work

- order creation
- order items
- review/edit
- confirmation
- controlled state transitions
- audit history
- tenant-scoped access

## Mandatory tests

- valid transitions
- invalid transitions
- cancellation
- failed order
- duplicate confirmation
- concurrent update behavior
- audit creation
- cross-tenant access
- incomplete order cannot bypass review rules

## Completion

State-machine and isolation tests pass. Create handoff, evidence, commit/tag `phase-08-complete`, then STOP.

## Phase 08 implementation record

- IMPLEMENTED: the order model (orders + order_items + order_events audit
  trail, migration 0008), the deterministic OrderCandidate → Order
  conversion (EXTRACTED → NEW; NEEDS_REVIEW → NEEDS_REVIEW with the review
  requirement retained; INVALID → no order; UNIQUE extraction_candidate_id +
  SAVEPOINT create-or-reuse; transactional), the enforced state machine
  (invalid transitions → 400 invalid_transition; every transition audited),
  the seller review API (list/get/events/PATCH items/confirm/process/
  complete/cancel — tenant-scoped, OWNER-only actions), the frontend orders
  workflow (/orders: list, inspect, confirm, process, complete, cancel +
  lifecycle states).
- NO invented values: no price fields (none exist in the extraction
  contract); the AI is never authoritative (no auto-confirmation anywhere).
- VERIFIED: 222/222 backend tests (15 orders tests), 41/41 frontend tests
  (11 orders), 3× consecutive stability runs (57/57 each), clean-DB
  migration + rollback/reapply, live run: candidate → order → confirm →
  process → complete → cancel (all audited).
- SIMULATOR_ONLY: no production Meta behavior; the simulator boundary is
  untouched.
