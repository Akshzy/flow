"""SIMULATOR_ONLY webhook request authentication.

A keyed HMAC-SHA256 over the raw request bytes with a server-controlled
secret — a Floww-defined contract for deterministic local testing.

- ENABLED only in development/test environments.
- DISABLED in production (the real Meta signature scheme is not implemented
  yet — the production webhook is blocked; no unauthenticated production
  endpoint exists).
- Authenticates the raw request bytes (not re-serialized JSON).
- Constant-time comparison (``hmac.compare_digest``).
- Never leaks the secret through logs or responses.

This is NOT Meta's production signature scheme (UNKNOWN_META, unverified) —
never represent it as such.
"""

import hashlib
import hmac

SIMULATOR_SIGNATURE_HEADER = "X-Floww-Simulator-Signature"


def simulator_signing_enabled(environment: str) -> bool:
    """Simulator authentication is enabled only outside production."""
    return environment != "production"


def compute_signature(secret: str, raw_body: bytes) -> str:
    """Compute the HMAC-SHA256 hex digest over the raw request bytes."""
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_simulator_signature(secret: str | None, raw_body: bytes, signature: str | None) -> bool:
    """Verify a simulator signature in constant time.

    Missing/invalid signature or missing secret → False.
    """
    if not secret or not signature:
        return False
    expected = compute_signature(secret, raw_body)
    return hmac.compare_digest(expected, signature)
