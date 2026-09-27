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
