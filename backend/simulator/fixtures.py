"""Deterministic simulator fixtures: stable identifiers, payload builders,
and request signing.

All identifiers are fake/stable (reproducible across runs); all customer
data is synthetic. No real Meta credentials and no real customer
information.
"""

import hashlib
import hmac
import json
from typing import Any

# --- Stable identifiers (deterministic across runs; fake) --------------------

SIMULATED_SENDER_A = "15550000001"
SIMULATED_SENDER_B = "15550000002"

CONNECTION_PHONE_NUMBER_ID = "555666444"
CONNECTION_WABA_ID = "999888777"
# Phase 9 (Instagram): the connection-identifier semantics for Instagram are
# SIMULATOR_ONLY — the real Instagram identifier semantics (Messenger API for
# Instagram) are UNKNOWN_META and must be reconciled with official docs.
INSTAGRAM_PHONE_NUMBER_ID = "777000111"
UNMAPPED_PHONE_NUMBER_ID = "000000000"  # no connection maps to this

MESSAGE_ID_VALID_1 = "wamid.sim-0001"
MESSAGE_ID_VALID_2 = "wamid.sim-0002"
MESSAGE_ID_VALID_3 = "wamid.sim-0003"

SIMULATED_EXTERNAL_TIMESTAMP = "2026-09-29T12:00:00Z"


def signature_for(secret: str, raw_body: bytes) -> str:
    """Compute the SIMULATOR_ONLY HMAC-SHA256 hex signature over raw bytes.

    Deterministic for the same secret + body.
    """
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def serialize(payload: dict[str, Any]) -> bytes:
    """Serialize a payload to bytes deterministically (sorted keys)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_event(
    message_id: str = MESSAGE_ID_VALID_1,
    sender: str = SIMULATED_SENDER_A,
    text: str = "Hello, I would like to order 2 pizzas",
    phone_number_id: str = CONNECTION_PHONE_NUMBER_ID,
    waba_id: str | None = CONNECTION_WABA_ID,
    timestamp: str = SIMULATED_EXTERNAL_TIMESTAMP,
) -> dict[str, Any]:
    """Build a valid text-message-shaped event (SIMULATOR_ONLY contract).

    Deterministic: the same arguments always produce the same payload.
    """
    event: dict[str, Any] = {
        "type": "messages",
        "phone_number_id": phone_number_id,
        "from": sender,
        "message_id": message_id,
        "text": {"body": text},
    }
    if waba_id is not None:
        event["waba_id"] = waba_id
    if timestamp is not None:
        event["timestamp"] = timestamp
    return event
