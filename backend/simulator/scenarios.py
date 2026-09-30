"""Deterministic simulator scenarios (Phase 5).

Each scenario submits events over HTTP through the real gateway boundary
and reports a deterministic expected outcome. Fake identifiers and
synthetic customer data only.

REAL META API TEST = BLOCKED (no credentials); these are SIMULATOR_ONLY
scenarios exercising the actual HTTP webhook boundary of this project.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from simulator.client import SimulatorClient
from simulator.fixtures import (
    CONNECTION_PHONE_NUMBER_ID,
    MESSAGE_ID_VALID_1,
    MESSAGE_ID_VALID_2,
    MESSAGE_ID_VALID_3,
    SIMULATED_SENDER_A,
    SIMULATED_SENDER_B,
    UNMAPPED_PHONE_NUMBER_ID,
    build_event,
    serialize,
    signature_for,
)


@dataclass
class ScenarioResult:
    name: str
    description: str
    expected: str
    actual_status: int | None = None
    actual_body: dict | None = field(default=None)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.actual_status is not None


def _body(response) -> dict | None:
    try:
        return response.json()
    except Exception:
        return None


async def run_all(
    client: SimulatorClient,
    *,
    oversized_secret_same: bool = True,
    persistence_failure_hook: Any = None,
) -> list[ScenarioResult]:
    """Run the deterministic scenario set in order.

    ``persistence_failure_hook``: optional callable (used by tests) that
    forces a persistence failure for scenario 15 and can then undo it for
    the recovery step.
    """
    results: list[ScenarioResult] = []

    async def record(name: str, description: str, expected: str, request) -> ScenarioResult:
        try:
            response = await request
            result = ScenarioResult(
                name, description, expected, response.status_code, _body(response)
            )
        except Exception as exc:  # network-level failure (e.g. server down)
            result = ScenarioResult(name, description, expected, None, None, str(exc))
        results.append(result)
        return result

    # 1. Valid text-message-shaped event.
    await record(
        "valid_text",
        "Valid text-message-shaped event",
        "202 accepted",
        client.submit(build_event(MESSAGE_ID_VALID_1)),
    )

    # 2. Another event from the same simulated sender (distinct message id).
    await record(
        "same_sender_second",
        "Another event from the same simulated sender",
        "202 accepted",
        client.submit(build_event(MESSAGE_ID_VALID_2, sender=SIMULATED_SENDER_A)),
    )

    # 3. Event from a different sender.
    await record(
        "different_sender",
        "Event from a different simulated sender",
        "202 accepted",
        client.submit(build_event(MESSAGE_ID_VALID_3, sender=SIMULATED_SENDER_B)),
    )

    # 4. Exact duplicate delivery (same bytes, same signature).
    await record(
        "exact_duplicate",
        "Exact duplicate delivery",
        "200 duplicate",
        client.submit(build_event(MESSAGE_ID_VALID_1)),
    )

    # 5. Multiple duplicate deliveries.
    for attempt in (1, 2, 3):
        await record(
            f"repeated_duplicate_{attempt}",
            "Repeated duplicate delivery",
            "200 duplicate",
            client.submit(build_event(MESSAGE_ID_VALID_1)),
        )

    # 6. Malformed JSON (valid signature over the malformed bytes).
    malformed = b"{not-json"
    await record(
        "malformed_json",
        "Malformed JSON payload",
        "422 validation_error",
        _submit_raw(client, malformed, signature_for(client.secret or "", malformed)),
    )

    # 7. Missing required fields (no message_id / from).
    await record(
        "missing_fields",
        "Payload missing required fields",
        "422 validation_error",
        client.submit({"type": "messages", "phone_number_id": CONNECTION_PHONE_NUMBER_ID}),
    )

    # 8. Invalid authentication (wrong secret).
    await record(
        "invalid_auth",
        "Invalid authentication (wrong secret)",
        "401 unauthorized",
        SimulatorClient(client.base_url, "wrong-secret").submit(build_event(MESSAGE_ID_VALID_2)),
    )

    # 9. Modified payload after signing (signature from the original body).
    original = build_event(MESSAGE_ID_VALID_2)
    original_raw = serialize(original)
    tampered = dict(original)
    tampered["text"] = {"body": "tampered content"}
    await record(
        "modified_after_signing",
        "Payload modified after signing",
        "401 unauthorized",
        client.submit(
            tampered,
            override_signature=signature_for(client.secret or "", original_raw),
        ),
    )

    # 10. Unknown connection (no connection maps to this phone_number_id).
    await record(
        "unknown_connection",
        "Unknown connection (unmapped phone_number_id)",
        "404 unknown_connection",
        client.submit(
            build_event("wamid.sim-0100", phone_number_id=UNMAPPED_PHONE_NUMBER_ID, waba_id=None)
        ),
    )

    # 11. Cross-tenant injection attempt (forged tenant_id in the payload —
    # must be ignored; the tenant resolves via the connection mapping).
    forged = build_event("wamid.sim-0101")
    forged["tenant_id"] = "00000000-0000-0000-0000-0000000000ff"
    await record(
        "cross_tenant_injection",
        "Cross-tenant injection attempt (forged tenant_id)",
        "202 accepted (forged tenant ignored)",
        client.submit(forged),
    )

    # 12. Unsupported event type.
    await record(
        "unsupported_event",
        "Unsupported event type",
        "422 validation_error",
        client.submit(
            {
                "type": "unsupported",
                "phone_number_id": CONNECTION_PHONE_NUMBER_ID,
                "from": SIMULATED_SENDER_A,
                "message_id": "wamid.sim-0102",
            }
        ),
    )

    # 13. Oversized payload (within the signed-body contract; the gateway
    # rejects it on the documented size limit).
    oversized = build_event("wamid.sim-0103", text="x" * 2_000_000)
    await record(
        "oversized_payload",
        "Oversized payload",
        "413 payload_too_large",
        _submit_raw(
            client,
            serialize(oversized),
            signature_for(client.secret or "", serialize(oversized)),
        ),
    )

    # 14. Concurrent duplicate submissions (same NEW message id, in
    # parallel) — a fresh id per run exercises the database-level race
    # (IntegrityError backstop); the stable fixtures above stay untouched.
    import uuid

    concurrent_id = f"wamid.sim-concurrent-{uuid.uuid4().hex[:8]}"
    concurrent = await asyncio.gather(
        *[client.submit(build_event(concurrent_id)) for _ in range(5)],
        return_exceptions=True,
    )
    statuses = [r.status_code for r in concurrent if hasattr(r, "status_code")]
    results.append(
        ScenarioResult(
            "concurrent_duplicates",
            "Concurrent duplicate submissions (5x)",
            "exactly one 202 accepted; the rest 200 duplicate",
            statuses[0] if statuses else None,
            {"statuses": statuses},
            None if len(statuses) == 5 else "network failure during concurrent run",
        )
    )

    # 15. Persistence failure and subsequent recovery (test hook only).
    if persistence_failure_hook is not None:
        persistence_failure_hook(force=True)
        await record(
            "persistence_failure",
            "Persistence failure (forced)",
            "500 internal_error; no accepted/duplicate ack",
            client.submit(build_event("wamid.sim-0199")),
        )
        persistence_failure_hook(force=False)
        await record(
            "persistence_recovery",
            "Recovery after persistence failure",
            "202 accepted",
            client.submit(build_event("wamid.sim-0199")),
        )

    return results


async def _submit_raw(client: SimulatorClient, raw: bytes, signature: str):
    """Submit pre-serialized raw bytes with a signature (failure scenarios)."""
    import httpx

    async with httpx.AsyncClient(timeout=client.timeout) as http:
        return await http.post(
            f"{client.base_url}/webhooks/whatsapp",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Floww-Simulator-Signature": signature,
            },
        )
