"""ASGI request-byte cap for multipart scan uploads before parser spooling."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

ASGIMessage = dict[str, Any]
ASGIReceive = Callable[[], Awaitable[ASGIMessage]]
ASGISend = Callable[[ASGIMessage], Awaitable[None]]


class _ScanRequestTooLarge(Exception):
    """Internal signal used to stop an oversized streaming request."""


class ScanBodySizeLimitMiddleware:
    """Bound the complete multipart body without buffering it in application memory."""

    def __init__(self, app, max_request_bytes: int, path: str) -> None:
        self.app = app
        self.max_request_bytes = max_request_bytes
        self.path = path

    async def __call__(self, scope: dict[str, Any], receive: ASGIReceive, send: ASGISend) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method", "").upper() != "POST"
            or scope.get("path") != self.path
        ):
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = 0
            if declared_length > self.max_request_bytes:
                await self._send_too_large(send)
                return

        received_bytes = 0
        response_started = False

        async def limited_receive() -> ASGIMessage:
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_request_bytes:
                    raise _ScanRequestTooLarge
            return message

        async def tracked_send(message: ASGIMessage) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _ScanRequestTooLarge:
            if not response_started:
                await self._send_too_large(send)

    async def _send_too_large(self, send: ASGISend) -> None:
        body = json.dumps(
            {
                "detail": {
                    "code": "image_too_large",
                    "message": "The upload exceeds the configured request size limit.",
                }
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
