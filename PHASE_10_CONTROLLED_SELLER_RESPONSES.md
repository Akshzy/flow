# PHASE 10 — CONTROLLED SELLER RESPONSES

## Objective

Implement controlled customer-facing responses only after inbound processing is reliable.

## Required work

- intent classification
- response policy
- approved response generation
- validation
- send workflow
- audit trail
- opt-in/configuration controls

## Safety rules

AI must not autonomously perform unsupported business actions.

Do not send a response when required information is unavailable or policy disallows it.

## Tests

- known intent
- unknown intent
- ambiguous intent
- malicious prompt
- unsupported request
- missing business information
- send failure
- duplicate send
- retry
- tenant isolation
- audit trail

## Completion

No uncontrolled autonomous messaging. Create handoff, evidence, commit/tag `phase-10-complete`, then STOP.
