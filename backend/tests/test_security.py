"""Unit tests: security primitives (password hashing, token handling)."""

from app.security import (
    TOKEN_BYTES,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_hash_password_uses_argon2id():
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed.startswith("$argon2id$")
    # The plaintext must not appear in the hash.
    assert "correct-horse-battery-staple" not in hashed


def test_hash_password_is_salted_and_unique():
    first = hash_password("same-password-123")
    second = hash_password("same-password-123")
    assert first != second  # unique salt per hash


def test_verify_password_correct_and_wrong():
    hashed = hash_password("right-password-123")
    assert verify_password(hashed, "right-password-123") is True
    assert verify_password(hashed, "wrong-password-123") is False


def test_verify_password_malformed_hash():
    assert verify_password("not-a-hash", "whatever") is False
    assert verify_password("", "whatever") is False


def test_generate_token_is_random_and_long():
    tokens = {generate_token() for _ in range(20)}
    assert len(tokens) == 20  # no collisions in a small sample
    for token in tokens:
        assert len(token) >= TOKEN_BYTES  # 256 bits of entropy, urlsafe


def test_hash_token_is_deterministic_and_differs_from_token():
    token = generate_token()
    first = hash_token(token)
    second = hash_token(token)
    assert first == second  # deterministic (used as the DB key)
    assert first != token  # the token itself is never persisted
    assert len(first) == 64  # SHA-256 hex digest
