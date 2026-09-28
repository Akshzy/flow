"""HTTP middleware: request ID assignment and structured request logging.

- Every request gets a fresh server-generated request ID (client-supplied IDs
  are not trusted), bound to the structlog context so all log records and
  error responses for the request can be correlated. The context is cleared
  at request start (keep-alive connections reuse one task; stale bindings
  must not leak between requests).
- This is a pure ASGI middleware (not BaseHTTPMiddleware): it runs in the
  connection's task, so the bound request ID remains visible to outer
  exception handlers (e.g. the 500 handler of ServerErrorMiddleware).
- Request logs contain method, path (without query string), status and
  duration only — request bodies and headers are never logged.
"""

import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status_holder: dict[str, int | None] = {"status": None}

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = MutableHeaders(scope=message)
                headers.append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # Exceptions that propagate past the application's exception
            # handlers. Logged (server-side) and re-raised; the request ID
            # stays bound so the record is correlated and the outer 500
            # handler can include it in the response.
            structlog.get_logger("http").exception(
                "http.request_failed",
                method=scope["method"],
                path=scope["path"],
            )
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        structlog.get_logger("http").info(
            "http.request",
            method=scope["method"],
            path=scope["path"],
            status=status_holder["status"],
            duration_ms=duration_ms,
        )
