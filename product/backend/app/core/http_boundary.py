"""Explicit resource errors, never truncated JSON or a partial monetary response."""

import asyncio

from fastapi import Request

from app.core.errors import error_response


class HttpBoundary:
    def __init__(
        self, app, request_bytes=1024 * 1024, response_bytes=10 * 1024 * 1024, work_seconds=90
    ):
        self.app = app
        self.request_bytes, self.response_bytes = request_bytes, response_bytes
        self.work_seconds = work_seconds

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        multipart = headers.get(b"content-type", b"").lower().startswith(b"multipart/form-data")
        # Specific proof/recovery guards retain their stricter JSON parsing/error contracts.
        if (
            scope.get("method") == "POST"
            and not multipart
            and not any(part in scope.get("path", "") for part in ("/proof/", "/recovery/"))
        ):
            chunks, total = [], 0
            try:
                async with asyncio.timeout(self.work_seconds):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        total += len(message.get("body", b""))
                        if total > self.request_bytes:
                            return await error_response(
                                Request(scope),
                                413,
                                "request_resource_limit",
                                "Request exceeds the JSON size limit",
                            )(scope, receive, send)
                        chunks.append(message.get("body", b""))
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await error_response(
                    Request(scope),
                    408,
                    "request_receive_timeout",
                    "Request receive budget exceeded",
                )(scope, receive, send)
            raw, delivered = b"".join(chunks), False
            upstream_receive = receive

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": raw, "more_body": False}
                return await upstream_receive()

            receive = replay

        start, captured, size, bounded_json, rejected = None, [], 0, False, False

        async def bounded_send(message):
            nonlocal start, size, bounded_json, rejected
            if message["type"] == "http.response.start":
                response_headers = dict(message.get("headers", []))
                bounded_json = (
                    response_headers.get(b"content-type", b"")
                    .lower()
                    .startswith(b"application/json")
                )
                if bounded_json:
                    start = message
                else:
                    await send(message)
                return
            if not bounded_json or message["type"] != "http.response.body":
                return await send(message)
            if rejected:
                return
            size += len(message.get("body", b""))
            if size > self.response_bytes:
                rejected = True
                captured.clear()
                return await error_response(
                    Request(scope),
                    413,
                    "response_resource_limit",
                    "Response exceeds the bounded presentation limit",
                )(scope, receive, send)
            captured.append(message.get("body", b""))
            if not message.get("more_body", False):
                await send(start)
                await send(
                    {"type": "http.response.body", "body": b"".join(captured), "more_body": False}
                )

        await self.app(scope, receive, bounded_send)
