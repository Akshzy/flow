"""Encrypted credential storage for platform connections.

Credential material (e.g. Meta access tokens) is encrypted at rest with
Fernet (AES-128-CBC + HMAC-SHA256, from the vetted ``cryptography``
package) using a server-side master key from the environment
(``CREDENTIAL_ENCRYPTION_KEY``). Plaintext credential material never
touches the database, logs, error messages, or API responses.

- Without the master key, storing/reading credentials fails with a clear
  ``ConfigError`` — the application starts fine without it (no credentials
  are stored until the connection flow is completed).
- The key is generated with ``Fernet.generate_key()`` (see .env.example).
- Tampered ciphertext raises ``InvalidToken``; the store converts it to a
  controlled application error.
- Key rotation is supported: ciphertexts can be re-encrypted under a new
  key by decrypting with the old key and encrypting with the new one
  (``rotate_key``).
"""

import json

import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.errors import AppError

logger = structlog.get_logger("credentials")


class CredentialStore:
    """Encrypts and decrypts connection credential material."""

    def __init__(self, master_key: str) -> None:
        if not master_key:
            raise AppError(
                "Credential encryption key is not configured.",
                code="credential_encryption_unavailable",
                status_code=503,
            )
        try:
            self._fernet = Fernet(master_key.encode("utf-8"))
        except ValueError as exc:
            # Invalid key format — fail clearly, never log the key material.
            logger.warning("credentials.invalid_key_format")
            raise AppError(
                "Credential encryption key has an invalid format.",
                code="credential_encryption_unavailable",
                status_code=503,
            ) from None

    def encrypt(self, credentials: dict) -> bytes:
        """Encrypt credential material. Never log the input or output."""
        plaintext = json.dumps(credentials, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes) -> dict:
        """Decrypt credential material. Never log the input or output."""
        try:
            plaintext = self._fernet.decrypt(ciphertext)
        except InvalidToken:
            # Wrong key or tampered ciphertext — a controlled error; the
            # connection must be re-authorized.
            logger.warning("credentials.decrypt_failed")
            raise AppError(
                "Stored connection credentials could not be decrypted; the "
                "connection must be re-authorized.",
                code="credential_decrypt_failed",
                status_code=503,
            ) from None
        return json.loads(plaintext.decode("utf-8"))

    def rotate_key(self, ciphertext: bytes, old_key: "CredentialStore") -> bytes:
        """Re-encrypt credential material under this store's key."""
        credentials = old_key.decrypt(ciphertext)
        return self.encrypt(credentials)
