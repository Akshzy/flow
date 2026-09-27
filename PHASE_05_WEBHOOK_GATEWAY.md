# PHASE 05 — WEBHOOK GATEWAY

## Objective

Build a secure, idempotent, asynchronous inbound event gateway.

## Required flow

Provider
→ verification
→ tenant/connection resolution
→ validation
→ persistence
→ idempotency
→ queue
→ prompt response

## Tests

- valid verification
- invalid verification
- valid signature if applicable
- invalid signature
- malformed payload
- unknown event
- duplicate event
- retry/replay
- unknown connection
- revoked connection
- database failure
- queue failure
- timeout
- prompt HTTP response
- no slow AI work inside request

## Security

Test tenant resolution and event ownership.

## Completion

All mandatory gateway tests pass. Create handoff, evidence, commit/tag `phase-05-complete`, then STOP.
