"""Simulator HTTP client.

Submits events over HTTP to the webhook gateway — the simulator never
bypasses the gateway or writes into the event database. The raw payload
bytes are signed (SIMULATOR_ONLY HMAC) and sent with the signature header.
"""

from typing import Any

import httpx

from simulator.fixtures import serialize, signature_for

SIMULATOR_SIGNATURE_HEADER = "X-Floww-Simulator-Signature"
WEBHOOK_PATH = "/webhooks/whatsapp"


class SimulatorClient:
    """Submits signed events over HTTP to the webhook gateway."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        secret: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.timeout = timeout

    def build_request(self, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        """Build the (body, headers) for a submission — deterministic."""
        raw = serialize(payload)
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers[SIMULATOR_SIGNATURE_HEADER] = signature_for(self.secret, raw)
        return raw, headers

    async def submit(
        self,
        payload: dict[str, Any],
        *,
        client: httpx.AsyncClient | None = None,
        override_signature: str | None = None,
        omit_signature: bool = False,
    ) -> httpx.Response:
        """Submit a payload over HTTP to the webhook gateway.

        ``override_signature``/``omit_signature`` support failure scenarios
        (modified payload after signing, invalid/missing authentication).
        """
        raw, headers = self.build_request(payload)
        if omit_signature:
            headers.pop(SIMULATOR_SIGNATURE_HEADER, None)
        elif override_signature is not None:
            headers[SIMULATOR_SIGNATURE_HEADER] = override_signature

        if client is not None:
            return await client.post(WEBHOOK_PATH, content=raw, headers=headers)
        async with httpx.AsyncClient(timeout=self.timeout) as standalone:
            return await standalone.post(
                f"{self.base_url}{WEBHOOK_PATH}", content=raw, headers=headers
            )
