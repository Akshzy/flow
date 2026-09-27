# PHASE 04 — WHATSAPP CONNECTION

## Objective

Implement the official WhatsApp connection/onboarding flow for a seller.

## Required work

Implement only the currently documented Meta flow verified in Phase 00/03 and re-verified now.

The system must:
- initiate connection
- validate callback/state
- associate connection with correct tenant
- store required connection metadata securely
- show connection status
- support disconnect/reconnect where supported

## Tests

- successful authorization
- user cancellation
- authorization denial
- invalid state
- expired state
- duplicate connection
- reconnect
- disconnect
- tenant isolation
- credential/logging security

## External verification

Where possible, perform a real Meta test with a development/test asset.

Clearly label:
VERIFIED / PARTIALLY VERIFIED / NOT VERIFIED.

## Completion

Do not fake a Meta result. Create handoff, evidence, commit/tag `phase-04-complete`, then STOP.
