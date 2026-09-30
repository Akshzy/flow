"""Webhook gateway HTTP endpoint (Phase 5, SIMULATOR_ONLY authentication).

Route: ``POST /webhooks/whatsapp``

Deterministic responses (SIMULATOR_ONLY contract, documented in
WEBHOOK_SPEC.md):

- 202 ``accepted``   — event persisted (PENDING_PROCESSING) before ack.
- 200 ``duplicate``  — idempotent duplicate delivery (no second event).
- 401 ``unauthorized`` — missing/invalid signature.
- 413 ``payload_too_large`` — request-size limit exceeded.
- 404 ``unknown_connection`` — no connected connection matches.
- 422 ``validation_error`` — malformed JSON / missing fields / unsupported
  event type.
- 500 ``internal_error`` — persistence failure (never acknowledged as
  successful ingestion).

Production behavior: the simulator authentication is DISABLED in production
and Meta's production webhook verification/signature scheme (UNKNOWN_META)
is not implemented — the endpoint is therefore explicitly blocked in
production (503 ``webhook_not_configured``). No unauthenticated production
endpoint exists.

The gateway never executes Phase 06 processing inside the HTTP request.
"""

import json
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session
from app.errors import AppError
from app.logging import get_request_id
from app.webhooks.auth import (
    SIMULATOR_SIGNATURE_HEADER,
    simulator_signing_enabled,
    verify_simulator_signature,
)
from app.webhooks.payload import PayloadValidationError, parse_payload
from app.webhooks.service import persist_event, resolve_connection

logger = structlog.get_logger("webhooks")

router = APIRouter(tags=["webhooks"])

DbSession = Annotated[AsyncSession, Depends(get_session)]


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}, "request_id": get_request_id()},
    )


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request, db: DbSession) -> JSONResponse:
    settings = request.app.state.settings

    # Production: simulator authentication is disabled and the real Meta
    # signature scheme is not implemented — the endpoint is blocked.
    if not simulator_signing_enabled(settings.environment):
        return _error_response(
            503,
            "webhook_not_configured",
            "Webhook authentication is not configured for production.",
        )

    # Request-size limit (documented): reject before reading/trusting the body.
    content_length = request.headers.get("content-length")
    if (
        content_length is not None
        and content_length.isdigit()
        and int(content_length) > settings.webhook_max_body_bytes
    ):
        logger.warning("webhook.payload_too_large")
        return _error_response(
            413,
            "payload_too_large",
            "Request body exceeds the allowed size.",
        )

    raw_body = await request.body()
    if len(raw_body) > settings.webhook_max_body_bytes:
        logger.warning("webhook.payload_too_large")
        return _error_response(413, "payload_too_large", "Request body exceeds the allowed size.")

    # SIMULATOR_ONLY authentication over the RAW request bytes
    # (constant-time comparison; the secret is never logged or returned).
    signature = request.headers.get(SIMULATOR_SIGNATURE_HEADER)
    if not verify_simulator_signature(settings.simulator_signing_secret, raw_body, signature):
        logger.warning("webhook.unauthorized")
        return _error_response(
            401,
            "unauthorized",
            "Missing or invalid webhook signature.",
        )

    # Payload validation (SIMULATOR_ONLY contract).
    try:
        payload = parse_payload(raw_body)
    except PayloadValidationError as exc:
        logger.warning("webhook.payload_invalid", reason=type(exc).__name__)
        return _error_response(422, "validation_error", str(exc))

    # Connection/tenant resolution (server-controlled mappings; the payload's
    # tenant fields are never trusted).
    try:
        connection = await resolve_connection(db, payload)
    except AppError as exc:
        return _error_response(exc.status_code, exc.code, exc.message)

    raw_payload = json.loads(raw_body.decode("utf-8"))
    try:
        event, created = await persist_event(db, connection, payload, raw_payload)
    except AppError as exc:
        return _error_response(exc.status_code, exc.code, exc.message)

    if not created:
        # Idempotent duplicate delivery: deterministic response, no second
        # event, processing history untouched.
        logger.info("webhook.duplicate", event_id=str(event.id))
        return JSONResponse(
            status_code=200,
            content={
                "status": "duplicate",
                "event_id": str(event.id),
                "processing_state": event.processing_state,
                "request_id": get_request_id(),
            },
        )

    # The event is durably persisted (PENDING_PROCESSING) before this ack.
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "event_id": str(event.id),
            "processing_state": event.processing_state,
            "request_id": get_request_id(),
        },
    )
