# PHASE 11 — EXCEL/CSV EXPORT

## Objective

Provide reliable export of confirmed orders.

## Required work

- export endpoint/UI
- stable column mapping
- CSV generation
- Excel-compatible output
- filtering by tenant/status/date as implemented

## Tests

- one order
- many orders
- empty result
- Unicode/Malayalam
- commas/quotes in address
- missing optional fields
- duplicate orders
- tenant isolation
- large export
- download integrity

## Completion

Exports must contain actual stored order data, not AI-generated display-only data. Create handoff, evidence, commit/tag `phase-11-complete`, then STOP.
