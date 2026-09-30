"""Deterministic Meta-compatible simulator (Phase 5).

The simulator exercises the ACTUAL HTTP webhook boundary: it signs raw
payload bytes and submits them to the webhook gateway over HTTP. It never
bypasses the gateway or writes into the event database.

Components:

- ``fixtures``   — reproducible fixtures (stable identifiers, synthetic
                   customer data), payload builders, request signing.
- ``client``     — the simulator HTTP client.
- ``scenarios``  — the deterministic scenario set.
- ``__main__``   — CLI entry point: ``python -m simulator``.

SIMULATOR_ONLY: the payload contract and the HMAC authentication are
Floww-defined for deterministic local testing — never presented as Meta's
production webhook scheme (UNKNOWN_META). Fake identifiers and synthetic
customer data only; no real Meta credentials and no real customer
information.
"""
