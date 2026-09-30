"""SIMULATOR_ONLY payload contract and validation.

This module defines the Floww webhook payload contract used by the
deterministic simulator. It is SIMULATOR_ONLY: the production Meta webhook
payload structure is UNKNOWN_META (not verified from official documentation
in this environment) and is not implemented yet.

Identifier fields used for connection resolution (``phone_number_id``,
``waba_id``) are VERIFIED_META identifiers (official Meta resources,
June 2026) — but the surrounding payload shape is the Floww simulator
contract.

Synthetic/fake identifiers and customer data only; never real customer
information.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The only supported inbound event type in the Phase 5 contract. Message
# normalization (Phase 6) will extend processing — not the gateway contract.
SUPPORTED_EVENT_TYPES = ("messages",)

EventType = Literal["messages"]


class SimulatorEventPayload(BaseModel):
    """SIMULATOR_ONLY inbound event contract (validated before persistence)."""

    model_config = ConfigDict(extra="ignore")

    type: EventType
    phone_number_id: str = Field(min_length=1)
    from_: str = Field(min_length=1, alias="from")
    message_id: str = Field(min_length=1)
    waba_id: str | None = None
    text: dict | None = None
    timestamp: datetime | None = None


def parse_payload(raw: bytes) -> SimulatorEventPayload:
    """Parse and validate the raw request bytes.

    Raises ``PayloadValidationError`` (mapped to a deterministic 422 by the
    router) for malformed JSON, missing required fields, unsupported event
    types, or schema violations.
    """
    import json

    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadValidationError("Malformed JSON payload.") from exc

    if not isinstance(document, dict):
        raise PayloadValidationError("Payload must be a JSON object.")

    try:
        return SimulatorEventPayload.model_validate(document)
    except ValueError as exc:
        raise PayloadValidationError("Payload failed validation.") from exc


class PayloadValidationError(Exception):
    """Raised for malformed/invalid webhook payloads (deterministic 422)."""


def dedup_key_for(platform: str, connection_id: str, external_event_id: str) -> str:
    """Build the database-level idempotency key.

    Scope: ``platform:connection_id:external_event_id`` — tenant-scoped
    through the resolved connection, so equivalent external IDs under
    different connections (different tenants) remain distinct events. The
    external event ID is required by the contract (missing required fields
    are rejected), so no payload-hash fallback exists.
    """
    return f"{platform}:{connection_id}:{external_event_id}"
