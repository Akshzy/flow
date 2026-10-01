"""Deterministic normalization boundary (Phase 6).

Raw persisted event → normalized internal message representation.

- Deterministic: the same input event always produces the same normalized
  result. No LLM, no probabilistic/fuzzy matching, no inference from names,
  text similarity, typing style, or metadata. Identity comes from explicit
  platform identifiers only (the simulator contract's ``from`` field).
- The normalized representation contains only what Phase 6 needs; the raw
  source event stays preserved in the Phase 05 event record
  (``webhook_events.raw_payload``) — the full external payload is not copied
  into downstream tables.
- Unsupported message types are never silently discarded: a persisted event
  with an unsupported type is recorded as FAILED with a reason (defensive —
  the Phase 5 gateway already rejects unsupported types at ingestion).
"""

from dataclasses import dataclass
from datetime import datetime

from app.errors import AppError
from app.models import WebhookEvent
from app.webhooks.payload import SimulatorEventPayload


@dataclass(frozen=True)
class NormalizedMessage:
    """The normalized internal message representation (Phase 6 needs only)."""

    platform: str
    tenant_id: str
    connection_id: str
    external_event_id: str | None
    external_user_id: str
    message_type: str
    body: str | None
    external_timestamp: datetime | None


def normalize_event(event: WebhookEvent) -> NormalizedMessage:
    """Normalize a persisted event into the internal message representation.

    Deterministic: re-validating the stored raw payload (it was validated at
    ingestion) yields the same result every time.

    Raises ``AppError`` (code ``unsupported_message_type``) if a persisted
    event carries an unsupported type — recorded as a processing failure by
    the consumer, never silently discarded.
    """
    payload = SimulatorEventPayload.model_validate(event.raw_payload)

    # Message type: "text" when the event carries a text body; otherwise the
    # event type itself (a "messages" event without a body stays typed
    # "messages" with body=None). Unsupported types fail with a reason.
    text_body = (payload.text or {}).get("body")
    message_type = "text" if isinstance(text_body, str) and text_body else payload.type
    if message_type not in ("text", "messages"):
        raise AppError(
            f"Unsupported message type: {message_type}",
            code="unsupported_message_type",
            status_code=422,
        )

    return NormalizedMessage(
        platform=event.platform,
        tenant_id=str(event.tenant_id),
        connection_id=str(event.connection_id),
        external_event_id=event.external_event_id,
        external_user_id=payload.from_,
        message_type=message_type,
        body=text_body if isinstance(text_body, str) else None,
        external_timestamp=payload.timestamp,
    )
