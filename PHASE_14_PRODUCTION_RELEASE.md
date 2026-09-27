# PHASE 14 — PRODUCTION RELEASE

## Objective

Deploy the verified application and prove the complete real-world flow.

## Required work

- production configuration
- frontend deployment
- backend deployment
- database
- worker/queue
- domain/TLS
- monitoring
- alerts
- backups
- operational runbook

## Mandatory end-to-end smoke test

Seller signs up
→ connects WhatsApp
→ customer sends real test message
→ Meta webhook arrives
→ event persists
→ message normalizes
→ AI extracts order
→ seller reviews
→ seller confirms
→ order appears
→ export works

Where Instagram is enabled, run the equivalent Instagram flow.

## Production evidence

Record:
- deployment version
- commit
- environment
- test account/assets
- timestamps
- observed results
- failures
- rollback procedure

## Completion

Production is COMPLETE only when the required real end-to-end path has evidence. Create final handoff, evidence, commit/tag `phase-14-complete`, then STOP.
