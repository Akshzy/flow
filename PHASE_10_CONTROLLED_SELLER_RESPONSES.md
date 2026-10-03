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

## Phase 10 implementation record

- IMPLEMENTED: the deterministic intent classification (from existing state:
  a conversation with a CONFIRMED order → order_confirmation; else
  unsupported — no LLM), the response policy (the tenant-level opt-in
  control `tenants.responses_enabled`), the approved-response generation (a
  deterministic template from the confirmed order's actual items; origin
  ai_suggested), validation, the send workflow (via the platform adapter
  boundary; the production send is UNKNOWN_META and refused — the failure is
  recorded, the response stays APPROVED/retryable, bounded by
  MAX_SEND_ATTEMPTS=5), the audit trail (response_events; the content is
  never logged), and the coherent Floww application shell + pages
  (Dashboard, Conversations + the response review UI, Orders + the detail
  with the delivery-address-missing state, Customers, Products (an honest
  roadmap state), Integrations, Settings, Login/Register polish).
- VERIFIED: 242/242 backend tests (8 response tests), 41/41 frontend tests,
  the live run: order confirmed → the response draft (ai_suggested, from
  the order's items) → approved → send refused (503, never a fake success);
  the pages verified live (10 pages HTTP 200).
- NO uncontrolled autonomous messaging: the approval is explicit; the send
  requires APPROVED + the opt-in control + the adapter.
