"""Deterministic message pipeline (Phase 6).

Consumes Phase 5's durable PENDING_PROCESSING events and deterministically
transforms them into Floww's internal messaging model:

    event → normalize → resolve customer → resolve conversation →
    persist message → mark event processed (one transaction)

Components:

- ``normalization`` — the deterministic normalization boundary (no LLM, no
  fuzzy matching; identity from explicit platform identifiers only).
- ``consumer``      — the deterministic consumer (transaction boundary,
  bounded retry policy).

SIMULATOR_ONLY input: the Phase 05 simulator contract is the authoritative
development input. Production Meta payload semantics are UNKNOWN_META and
not invented.
"""
