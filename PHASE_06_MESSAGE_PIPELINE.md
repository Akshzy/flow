# PHASE 06 — MESSAGE PIPELINE

## Objective

Normalize inbound WhatsApp events into platform-independent internal messages.

## Required work

- conversation creation/update
- customer association
- normalized message schema
- message persistence
- ordering/timestamps
- deduplication
- supported message types

## Tests

- new conversation
- existing conversation
- duplicate event
- duplicate message
- multiple customers
- missing optional fields
- unsupported message type
- malformed event
- event ordering
- tenant isolation
- database failure

## Completion

Core pipeline works without AI. Create handoff, evidence, commit/tag `phase-06-complete`, then STOP.
