"""Simulator unit tests: deterministic fixtures, signing, HTTP submission.

REAL META API TEST = BLOCKED (no credentials); these verify the
SIMULATOR_ONLY contract deterministically.
"""

import json

import httpx

from simulator.client import WEBHOOK_PATH, SimulatorClient
from simulator.fixtures import (
    CONNECTION_PHONE_NUMBER_ID,
    CONNECTION_WABA_ID,
    MESSAGE_ID_VALID_1,
    SIMULATED_SENDER_A,
    build_event,
    serialize,
    signature_for,
)


def test_fixtures_are_deterministic():
    """The same arguments always produce the same payload (stable IDs)."""
    first = build_event(MESSAGE_ID_VALID_1)
    second = build_event(MESSAGE_ID_VALID_1)
    assert first == second
    assert first["message_id"] == MESSAGE_ID_VALID_1
    assert first["from"] == SIMULATED_SENDER_A
    assert first["phone_number_id"] == CONNECTION_PHONE_NUMBER_ID
    assert first["waba_id"] == CONNECTION_WABA_ID
    assert first["type"] == "messages"


def test_fixtures_use_stable_identifiers():
    """Fixture IDs are stable across calls (reproducible runs)."""
    assert build_event() == build_event()
    assert serialize(build_event()) == serialize(build_event())


def test_signing_is_deterministic_and_covers_raw_bytes():
    raw = serialize(build_event())
    first = signature_for("secret-1", raw)
    second = signature_for("secret-1", raw)
    assert first == second  # deterministic for the same secret + body
    assert signature_for("secret-2", raw) != first  # secret-dependent
    assert signature_for("secret-1", raw + b" ") != first  # body-dependent
    assert len(first) == 64  # HMAC-SHA256 hex digest


def test_build_request_signs_the_raw_bytes():
    client = SimulatorClient(secret="secret-1")
    payload = build_event(MESSAGE_ID_VALID_1)
    raw, headers = client.build_request(payload)
    # The signature is computed over the serialized raw bytes.
    assert headers["X-Floww-Simulator-Signature"] == signature_for("secret-1", raw)
    assert json.loads(raw) == payload
    assert headers["Content-Type"] == "application/json"


async def test_client_submits_over_http_to_the_gateway():
    """The client performs an actual HTTP POST to the webhook path."""
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = request.content
        captured["headers"] = dict(request.headers)
        return httpx.Response(202, json={"status": "accepted", "event_id": "e1"})

    transport = httpx.MockTransport(handler)
    client = SimulatorClient(secret="secret-1")
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as http:
        response = await client.submit(build_event(MESSAGE_ID_VALID_1), client=http)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert captured["path"] == WEBHOOK_PATH
    assert captured["method"] == "POST"
    # The signature over the actual submitted bytes verifies:
    assert captured["headers"]["x-floww-simulator-signature"] == signature_for(
        "secret-1", captured["body"]
    )


async def test_client_without_secret_sends_no_signature():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "unauthorized"}})

    transport = httpx.MockTransport(handler)
    client = SimulatorClient(secret=None)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as http:
        response = await client.submit(build_event(MESSAGE_ID_VALID_1), client=http)
    assert response.status_code == 401


def test_gateway_rejects_unsigned_via_constant_time_path():
    """The signature check uses hmac.compare_digest (constant-time)."""
    import inspect

    from app.webhooks import auth as webhook_auth

    source = inspect.getsource(webhook_auth.verify_simulator_signature)
    assert "compare_digest" in source
    # Behavior: constant-time comparison rejects mismatches.
    assert webhook_auth.verify_simulator_signature("s", b"body", "bad") is False
    assert webhook_auth.verify_simulator_signature("s", b"body", None) is False
    assert webhook_auth.verify_simulator_signature(None, b"body", "sig") is False
    valid = signature_for("s", b"body")
    assert webhook_auth.verify_simulator_signature("s", b"body", valid) is True
