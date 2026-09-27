# RISKS

Track:

| ID | Risk | Severity | Probability | Mitigation | Status |
|---|---|---:|---:|---|---|
| R-001 | External API changes | High | Medium | Verify official docs per phase | Open |
| R-002 | Cross-tenant data leakage | Critical | Low | Isolation tests | Open |
| R-003 | AI extraction errors | High | Medium | Schema + deterministic validation + review | Open |
| R-004 | Webhook duplication | High | High | Idempotency | Open |
| R-005 | Secret leakage | Critical | Low | Secret scanning + env/secrets | Open |
