"""Meta integration abstraction (narrow adapter boundary).

All Meta-specific logic is isolated here; the rest of Floww depends on
normalized connection state, never on raw Meta HTTP calls.

Verified current Meta behavior (official Meta resources, June 2026 — see
INTEGRATIONS.md):

- Embedded Signup v4 is the current unified onboarding architecture
  (WhatsApp, Messenger, Instagram Direct via one streamlined flow; migration
  path from legacy v2/v3 exists).
- The WhatsApp account model is evolving: the WhatsApp Business Account
  (WABA) is being split into a WhatsApp Account (WAAC, phone numbers) and a
  Messaging Account (PMA, templates and billing); this affects Embedded
  Signup and Cloud API calls.
- Usernames + the Business Scoped User ID (BSUID) will replace phone numbers
  for users who adopt usernames (30-day phone number visibility rule).

NOT verified (implementation details live in the video/dashboard, not the
extractable static documentation): exact Embedded Signup v4 configuration
parameters, OAuth scopes, token exchange endpoints, callback payload
structures, and de-authorization endpoints. Those operations are therefore
NOT implemented — they raise a controlled ``meta_not_configured`` error
rather than guessing undocumented behavior (see the adapter methods).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from app.credential_store import CredentialStore
from app.models import ConnectionStatus, Platform, PlatformConnection

logger = structlog.get_logger("meta")

# Set by the phase that implements the Meta authorization flow, after the
# current Embedded Signup v4 configuration/scopes are verified against
# official documentation. No speculative scope strings are hard-coded here.
META_AUTHORIZATION_IMPLEMENTED = False


class MetaAuthorizationNotConfiguredError(Exception):
    """Raised by Meta-facing operations that are not yet implemented.

    The current official Embedded Signup v4 configuration (session
    parameters, scopes, token exchange, callback payloads) has not been
    verified from official documentation in this environment, so these
    operations refuse to guess.
    """

    def __init__(
        self, message: str = "Meta authorization is not configured yet."
    ) -> None:
        super().__init__(message)


def normalize_identifier(value: Any) -> str | None:
    """Normalize a Meta platform identifier to its string form.

    Meta identifiers are numeric strings; they are never treated as integers
    (precision loss) and never as secrets.
    """
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


class MetaConnectionService:
    """Tenant-owned WhatsApp connection lifecycle (Meta-specific logic)."""

    def __init__(self, credential_store: CredentialStore | None = None) -> None:
        self._credential_store = credential_store

    # --- Lifecycle state transitions (deterministic, locally verified) ------

    def initiate(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> PlatformConnection:
        """Create an initiated connection record.

        The Meta authorization step itself is not implemented yet (see
        META_AUTHORIZATION_IMPLEMENTED); this creates the lifecycle record
        only.
        """
        now = datetime.now(UTC)
        return PlatformConnection(
            tenant_id=tenant_id,
            platform=Platform.WHATSAPP,
            status=ConnectionStatus.INITIATED,
            connected_by_user_id=user_id,
            initiated_at=now,
        )

    def connect(
        self,
        connection: PlatformConnection,
        *,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        account_identifiers: dict | None = None,
        credentials: dict | None = None,
        user_id: uuid.UUID | None = None,
    ) -> PlatformConnection:
        """Mark a connection as connected with verified-shape identifiers.

        ``waba_id``/``phone_number_id`` are normalized Meta identifiers;
        ``account_identifiers`` is the extension point for the evolving
        account model (WAAC/PMA). ``credentials`` (e.g. an access token) is
        encrypted at rest via the credential store and never stored in
        plaintext — this requires a configured credential store.
        """
        if connection.status == ConnectionStatus.CONNECTED:
            raise ValueError("Connection is already connected.")
        now = datetime.now(UTC)
        connection.status = ConnectionStatus.CONNECTED
        connection.waba_id = normalize_identifier(waba_id)
        connection.phone_number_id = normalize_identifier(phone_number_id)
        connection.account_identifiers = account_identifiers
        if credentials is not None:
            if self._credential_store is None:
                raise MetaAuthorizationNotConfiguredError(
                    "Credential storage is not configured."
                )
            connection.credentials_encrypted = self._credential_store.encrypt(
                credentials
            )
        if user_id is not None:
            connection.connected_by_user_id = user_id
        connection.connected_at = now
        logger.info(
            "connection.connected",
            tenant_id=str(connection.tenant_id),
            connection_id=str(connection.id),
        )
        return connection

    def disconnect(self, connection: PlatformConnection) -> PlatformConnection:
        """Mark a connected connection as disconnected (history kept)."""
        now = datetime.now(UTC)
        connection.status = ConnectionStatus.DISCONNECTED
        connection.disconnected_at = now
        # Credential material is destroyed on disconnect (least exposure).
        connection.credentials_encrypted = None
        logger.info(
            "connection.disconnected",
            tenant_id=str(connection.tenant_id),
            connection_id=str(connection.id),
        )
        return connection

    # --- Meta-facing operations (NOT implemented; no guessing) ---------------

    def build_authorization_url(self) -> str:
        """Build the Meta authorization URL.

        NOT IMPLEMENTED: the current Embedded Signup v4 configuration
        (session parameters and scopes) has not been verified from official
        documentation in this environment. No speculative URL is constructed.
        """
        raise MetaAuthorizationNotConfiguredError(
            "Meta authorization configuration (Embedded Signup v4 parameters "
            "and scopes) has not been verified yet."
        )

    def validate_authorization_callback(self, payload: dict) -> dict:
        """Validate a Meta authorization result.

        NOT IMPLEMENTED: the current callback payload structure has not been
        verified from official documentation in this environment.
        """
        raise MetaAuthorizationNotConfiguredError(
            "Meta authorization callback handling has not been verified yet."
        )

    def exchange_code_for_token(self, authorization_code: str) -> dict:
        """Exchange an authorization code for connection credentials.

        NOT IMPLEMENTED: the current token exchange endpoint has not been
        verified from official documentation in this environment. No
        speculative endpoint is contacted; the code is never logged.
        """
        raise MetaAuthorizationNotConfiguredError(
            "Meta token exchange has not been verified yet."
        )

    def deauthorize(self, connection: PlatformConnection) -> None:
        """Revoke the platform-side authorization.

        NOT IMPLEMENTED: the current de-authorization endpoint/behavior has
        not been verified from official documentation in this environment.
        The Floww-side disconnect (``disconnect``) is implemented; the
        platform-side revocation is a manual action until verified.
        """
        raise MetaAuthorizationNotConfiguredError(
            "Platform-side de-authorization has not been verified yet."
        )
