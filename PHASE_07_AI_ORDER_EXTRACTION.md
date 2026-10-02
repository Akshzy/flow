# PHASE 07 — AI ORDER EXTRACTION

## Objective

Convert conversation content into a structured order candidate without allowing the model to invent facts.

## Required work

- strict extraction schema
- model adapter
- structured output validation
- normalization
- required-field validation
- ambiguity detection
- extraction persistence
- human-review candidate creation

## Mandatory test corpus

Test:
- complete order
- missing phone
- missing address
- missing quantity
- missing size
- multiple products
- multiple orders
- corrections
- cancellation
- contradictory messages
- Malayalam
- Manglish
- typos
- unrelated conversation
- prompt injection
- ambiguous values

## Hard rule

Missing information remains missing.

The model must not invent customer/order data.

## Completion

AI tests and deterministic validation tests pass. Create handoff, evidence, commit/tag `phase-07-complete`, then STOP.

## Phase 07 implementation record (recovery run)

- RECOVERED: the interrupted run's corrupted state (mangled tool edits,
  a weakened test, broken working-tree remnants) was audited and repaired
  from the clean baseline commit.
- IMPLEMENTED: strict extraction schema (OrderItem/OrderCandidate), the
  deterministic AI test double extended to the mandatory test corpus
  (SIMULATOR_ONLY for the AI layer), structured-output validation,
  required-field validation (missing key → NEEDS_REVIEW), ambiguity
  detection (contradictory quantities / unresolvable references →
  NEEDS_REVIEW), extraction persistence (idempotent by message_id,
  migration 0006), pipeline integration (extraction after the message is
  durable; extraction-retry gap fixed), the order_extraction_candidates
  model.
- BUGS FIXED: the messages.updated_at model/migration mismatch (migration
  0007), 51 wrong model annotations (Mapped[Uuid]/Mapped[Text]/dropped
  timezone), a duplicate ExtractionStatus, the deprecated @validator, the
  extraction-retry gap.
- VERIFIED: 207/207 backend tests (stability-verified ×2); 22/22 extraction
  tests (15 corpus); the corpus covers all mandatory categories (complete
  order, missing phone/address/quantity/size, multiple products, multiple
  orders, corrections, cancellation, contradictory messages, Malayalam,
  Manglish, typos, unrelated conversation, prompt injection, ambiguous
  values) — no invention anywhere (verified by tests).
- NOT IMPLEMENTED: the real AI provider integration (a later phase; never
  faked) — the deterministic test double is SIMULATOR_ONLY for the AI
  layer.
