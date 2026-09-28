"""Security primitives: password hashing and session token handling.

- Passwords are hashed with argon2id (the OWASP-recommended memory-hard
  KDF, via argon2-cffi). Plaintext passwords are never stored or logged.
- Session tokens are random, server-generated opaque tokens. Only the
  SHA-256 hash of a token is persisted, so a database leak does not expose
  usable credentials. Expiry is enforced at lookup time.
- No custom cryptography is implemented; both primitives use vetted
  standard libraries.
"""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2id with library defaults (m=64MiB, t=3, p=4).
_hasher = PasswordHasher()

TOKEN_BYTES = 32  # 256-bit random tokens


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id. Never log the input."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against a stored argon2id hash.

    Returns False for wrong passwords and malformed hashes; never raises.
    """
    try:
        _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return True


def generate_token() -> str:
    """Generate a cryptographically random session token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token (the persisted form)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
