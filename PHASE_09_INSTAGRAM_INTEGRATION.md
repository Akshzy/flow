# PHASE 09 — INSTAGRAM INTEGRATION

## Objective

Add Instagram through the currently documented official Meta integration and reuse the existing message/order pipeline.

## Required work

- verify current official Instagram requirements
- authorization/connection
- webhook/events
- normalization adapter
- tenant mapping
- message persistence

## Tests

- authorization success/failure
- invalid callback
- webhook verification
- duplicate events
- unknown connection
- tenant isolation
- message normalization
- failure/retry behavior

## Architecture test

Instagram must feed the same internal message/order pipeline rather than creating a separate order engine.

## Completion

External verification must be explicitly classified. Create handoff, evidence, commit/tag `phase-09-complete`, then STOP.
