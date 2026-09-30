"""Webhook gateway package (Phase 5).

Separate components (per WEBHOOK_SPEC.md and ARCHITECTURE.md):

- ``auth``      — SIMULATOR_ONLY request authentication (HMAC over raw bytes).
- ``payload``   — the SIMULATOR_ONLY payload contract + validation.
- ``service``   — connection/tenant resolution, idempotency, event
                  persistence and lifecycle (no message normalization,
                  customer management, AI or order logic).
- ``router``    — the HTTP endpoint (size limit, error handling).

REAL META BOUNDARY: BLOCKED — Meta's production webhook verification
(``hub.mode``/``hub.challenge``/``hub.verify_token``) and signature scheme
(``X-Hub-Signature-256``) could not be verified from official documentation
in this environment (the docs pages are client-rendered; see
INTEGRATIONS.md). The production Meta webhook is therefore NOT implemented;
the SIMULATOR_ONLY mechanism below is a Floww-defined contract for
deterministic local testing and is never presented as Meta's production
scheme.
"""
