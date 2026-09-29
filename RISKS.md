# RISKS

Track:

| ID | Risk | Severity | Probability | Mitigation | Status |
|---|---|---|---:|---:|---|
| R-001 | External API changes | High | Medium | Verify official docs per phase | Open |
| R-002 | Cross-tenant data leakage | Critical | Low | Isolation tests (Phase 2: cross-tenant GET/UPDATE/DELETE + IDOR checks pass) | Mitigated — re-audit in Phase 13 |
| R-003 | AI extraction errors | High | Medium | Schema + deterministic validation + review | Open |
| R-004 | Webhook duplication | High | High | Idempotency | Open |
| R-005 | Secret leakage | Critical | Low | Secret scanning + env/secrets | Open |
| R-006 | Session token theft (localStorage XSS) | High | Low | Tokens hashed at rest; logout invalidation; cookie hardening in Phase 13 | Open |
| R-007 | Privacy policy not publicly hosted — Meta app review blocked | Medium | High | Deploy frontend; configure Meta Privacy Policy URL to public /privacy | Open — MANUAL ACTION REQUIRED |
| R-008 | Embedded Signup v4 specifics unverified (scopes/tokens/callbacks) — implementation blocked | High | High | Adapter refuses to guess; verify official docs in the implementing phase | Open — documented in ADR-010 |
