# PHASE 12 — BILLING

## Objective

Add subscription/usage billing only after core product value is working.

## Required work

- plan model
- subscription state
- usage tracking
- limits
- billing provider adapter
- webhook/event handling
- entitlement checks

## Tests

- new subscription
- duplicate billing event
- failed payment
- cancellation
- renewal
- plan limit
- over-limit behavior
- tenant isolation
- billing webhook verification

## Completion

Billing state must be deterministic and auditable. Create handoff, evidence, commit/tag `phase-12-complete`, then STOP.
