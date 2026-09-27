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
