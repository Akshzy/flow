"""Unit tests: Meta connection adapter + credential store (deterministic).

These tests use locally generated test tokens — they do NOT contact the
real Meta API.

REAL META API TEST = BLOCKED (required credentials unavailable in this
environment; no Meta connectivity is claimed or faked).
"""

import uuid

import pytest
from cryptography.fernet import Fernet

from app.credential_store import CredentialStore
from app.errors import AppError
from app.meta import (
    MetaAuthorizationNotConfiguredError,
    MetaConnectionService,
    normalize_identifier,
)


@pytest.fixture()
def credential_store() -> CredentialStore:
    return CredentialStore(Fernet.generate_key().decode())


@pytest.fixture()
def service(credential_store: CredentialStore) -> MetaConnectionService:
    return MetaConnectionService(credential_store)


def test_normalize_identifier():
    assert normalize_identifier("12345") == "12345"
    assert normalize_identifier("  12345  ") == "12345"
    assert normalize_identifier(12345) == "12345"  # numeric input → string
    assert normalize_identifier(None) is None
    assert normalize_identifier("   ") is None
    # Large identifiers are never converted to int (no precision loss).
    big = "9" * 25
    assert normalize_identifier(big) == big


# --- Credential store ---------------------------------------------------------


def test_credential_store_encrypts_at_rest(credential_store: CredentialStore):
    """Plaintext credential material must never appear in the ciphertext."""
    secrets_payload = {
        "access_token": "super-secret-test-token-material",
        "token_type": "bearer",
    }
    ciphertext = credential_store.encrypt(secrets_payload)
    assert isinstance(ciphertext, bytes)
    # The ciphertext is not the plaintext and does not contain it.
    assert b"super-secret-test-token-material" not in ciphertext
    # Decryption returns the original material.
    assert credential_store.decrypt(ciphertext) == secrets_payload


def test_credential_store_ciphertext_is_nondeterministic(
    credential_store: CredentialStore,
):
    payload = {"access_token": "same-token"}
    first = credential_store.encrypt(payload)
    second = credential_store.encrypt(payload)
    assert first != second  # random IV per encryption


def test_credential_store_rejects_bad_keys():
    with pytest.raises(AppError) as excinfo:
        CredentialStore("not-a-valid-fernet-key")
    assert excinfo.value.code == "credential_encryption_unavailable"
    with pytest.raises(AppError):
        CredentialStore("")


def test_credential_store_rejects_tampered_or_wrong_key_ciphertext(
    credential_store: CredentialStore,
):
    ciphertext = credential_store.encrypt({"access_token": "secret-token-1"})
    other = CredentialStore(Fernet.generate_key().decode())
    with pytest.raises(AppError) as excinfo:
        other.decrypt(ciphertext)
    assert excinfo.value.code == "credential_decrypt_failed"

    tampered = bytearray(ciphertext)
    tampered[10] ^= 0xFF
    with pytest.raises(AppError):
        credential_store.decrypt(bytes(tampered))


def test_credential_store_key_rotation(credential_store: CredentialStore):
    new_store = CredentialStore(Fernet.generate_key().decode())
    ciphertext = credential_store.encrypt({"access_token": "rotate-me-1"})
    rotated = new_store.rotate_key(ciphertext, credential_store)
    # The old key can no longer decrypt; the new key can.
    with pytest.raises(AppError):
        credential_store.decrypt(rotated)
    assert new_store.decrypt(rotated) == {"access_token": "rotate-me-1"}


# --- Connection lifecycle state machine ----------------------------------------


def test_initiate_creates_initiated_record(service: MetaConnectionService):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    connection = service.initiate(tenant_id, user_id)
    assert connection.tenant_id == tenant_id
    assert connection.connected_by_user_id == user_id
    assert connection.status == "initiated"
    assert connection.initiated_at is not None
    assert connection.connected_at is None
    assert connection.credentials_encrypted is None


def test_connect_marks_connected_with_normalized_identifiers(
    service: MetaConnectionService,
):
    connection = service.initiate(uuid.uuid4(), uuid.uuid4())
    connected = service.connect(
        connection,
        waba_id="  1111111111  ",
        phone_number_id="2222222222",
        account_identifiers={"note": "account model extension point"},
    )
    assert connected.status == "connected"
    assert connected.waba_id == "1111111111"  # normalized
    assert connected.phone_number_id == "2222222222"
    assert connected.connected_at is not None


def test_connect_encrypts_credentials_at_rest(service: MetaConnectionService):
    connection = service.initiate(uuid.uuid4(), uuid.uuid4())
    connected = service.connect(
        connection, credentials={"access_token": "secret-test-token-2"}
    )
    assert connected.credentials_encrypted is not None
    # The plaintext token is never stored on the record.
    assert b"secret-test-token-2" not in (connected.credentials_encrypted or b"")
    # The store can decrypt it (server-side only).
    assert service._credential_store is not None
    assert service._credential_store.decrypt(connected.credentials_encrypted) == {
        "access_token": "secret-test-token-2"
    }


def test_connect_without_credential_store_fails_clearly():
    service = MetaConnectionService(credential_store=None)
    connection = service.initiate(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(MetaAuthorizationNotConfiguredError):
        service.connect(connection, credentials={"access_token": "secret"})


def test_connect_already_connected_fails(service: MetaConnectionService):
    connection = service.initiate(uuid.uuid4(), uuid.uuid4())
    service.connect(connection, waba_id="111")
    with pytest.raises(ValueError):
        service.connect(connection, waba_id="222")


def test_disconnect_destroys_credentials_and_keeps_history(
    service: MetaConnectionService,
):
    connection = service.initiate(uuid.uuid4(), uuid.uuid4())
    service.connect(connection, credentials={"access_token": "secret-test-token-3"})
    disconnected = service.disconnect(connection)
    assert disconnected.status == "disconnected"
    assert disconnected.disconnected_at is not None
    # Credential material is destroyed (least exposure).
    assert disconnected.credentials_encrypted is None
    # Lifecycle timestamps remain for audit/history.
    assert disconnected.connected_at is not None


def test_meta_facing_operations_refuse_to_guess(service: MetaConnectionService):
    """Unverified Meta operations raise a controlled error — never guess."""
    connection = service.initiate(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(MetaAuthorizationNotConfiguredError):
        service.build_authorization_url()
    with pytest.raises(MetaAuthorizationNotConfiguredError):
        service.validate_authorization_callback({"anything": True})
    with pytest.raises(MetaAuthorizationNotConfiguredError):
        service.exchange_code_for_token("auth-code-value")
    with pytest.raises(MetaAuthorizationNotConfiguredError):
        service.deauthorize(connection)
