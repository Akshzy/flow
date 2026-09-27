# PHASE 13 — SECURITY AND PRODUCTION HARDENING

## Objective

Audit the complete application before production.

## Required work

- dependency audit
- secret scan
- authentication audit
- authorization audit
- tenant isolation audit
- webhook security review
- rate limits
- input validation
- PII/logging review
- backup strategy
- recovery test
- observability
- error tracking
- operational documentation

## Mandatory tests

- cross-tenant attack cases
- IDOR-style access attempts
- malformed payloads
- rate-limit behavior
- secret exposure checks
- revoked credential behavior
- dependency vulnerabilities
- backup restore
- failure recovery

## Completion

Any critical unresolved security issue blocks completion. Create handoff, evidence, commit/tag `phase-13-complete`, then STOP.
