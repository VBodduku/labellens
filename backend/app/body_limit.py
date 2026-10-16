"""ASGI middleware that caps request bodies while they stream in.

Unlike a Content-Length check it also stops chunked uploads that send no length. The body is
replayed to the app unchanged when it is within the limit.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.errors import ApiError

JSON_BODY_LIMIT = 4 * 1024 * 1024


class BodyLimit:
    def __init__(self, app: ASGIApp, scan_limit: Callable[[], int], respond: Callable[[ApiError], Any]) -> None:
        self.app = app
        self.scan_limit = scan_limit
        self.respond = respond          # ApiError -> ASGI response (the app's ErrorResponse renderer)

    def _limit(self, scope: Scope) -> tuple[int, ApiError]:
        if scope["path"] == "/api/scan":
            limit = self.scan_limit()
            return limit, ApiError(413, "BAD_IMAGE", f"The upload is larger than {limit // (1024 * 1024)} MB.")
        return JSON_BODY_LIMIT, ApiError(413, "VALIDATION", "The request body is too large.")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        limit, error = self._limit(scope)
        length = dict(scope["headers"]).get(b"content-length", b"")
        if length.isdigit() and int(length) > limit:
            await self.respond(error)(scope, receive, send)
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                await self.respond(error)(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
