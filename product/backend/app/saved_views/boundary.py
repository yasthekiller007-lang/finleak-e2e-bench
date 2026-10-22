"""Bound every personal-view write, including PATCH and DELETE; never log bodies."""

import asyncio
import json

from starlette.requests import Request

from app.core.errors import error_response


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Repeated JSON field")
        result[key] = value
    return result


class SavedViewBodyGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or "/financial/saved-views" not in scope.get("path", "")
            or scope.get("method") not in {"POST", "PATCH", "DELETE"}
        ):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if not headers.get(b"content-type", b"").lower().startswith(b"application/json"):
            return await error_response(
                Request(scope), 415, "SAVED_VIEW_JSON", "Use a JSON personal view request"
            )(scope, receive, send)
        chunks, total = [], 0
        try:
            async with asyncio.timeout(30):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    total += len(message.get("body", b""))
                    if total > 16384:
                        return await error_response(
                            Request(scope),
                            413,
                            "SAVED_VIEW_SIZE",
                            "Personal view request exceeds its size limit",
                        )(scope, receive, send)
                    chunks.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
            raw = b"".join(chunks)
            json.loads(raw, object_pairs_hook=unique_object)
        except (ValueError, UnicodeError, RecursionError):
            return await error_response(
                Request(scope), 422, "SAVED_VIEW_JSON", "Invalid personal view JSON"
            )(scope, receive, send)
        except TimeoutError:
            return await error_response(
                Request(scope), 408, "SAVED_VIEW_RECEIVE", "Personal view receive budget exceeded"
            )(scope, receive, send)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)
