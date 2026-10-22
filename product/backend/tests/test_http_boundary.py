import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.http_boundary import HttpBoundary
from app.main import create_app


def scope(
    path="/api/v1/resource", *, content_type=b"application/json", method="POST", content_length=None
):
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(b"content-type", content_type)]
        + ([(b"content-length", content_length)] if content_length is not None else []),
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
    }


async def exercise(app, messages, **changes):
    pending = iter(messages)
    sent = []

    async def receive():
        return next(pending)

    async def send(message):
        sent.append(message)

    await app(scope(**changes), receive, send)
    return sent


@pytest.mark.parametrize("deceptive_length", [b"0", b"9999999"])
def test_actual_chunked_json_size_is_bounded_before_parser(deceptive_length):
    import asyncio

    called = []

    async def endpoint(scope, receive, send):
        called.append(True)

    sent = asyncio.run(
        exercise(
            HttpBoundary(endpoint, request_bytes=5),
            [
                {"type": "http.request", "body": b"123", "more_body": True},
                {"type": "http.request", "body": b"456", "more_body": False},
            ],
            content_length=deceptive_length,
        )
    )
    assert not called and sent[0]["status"] == 413
    assert "request_resource_limit" in sent[1]["body"].decode()


def test_json_response_never_leaks_a_partial_financial_or_sensitive_prefix():
    import asyncio

    async def endpoint(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"private":', "more_body": True})
        await send({"type": "http.response.body", "body": b'"sentinel"}', "more_body": False})

    sent = asyncio.run(exercise(HttpBoundary(endpoint, response_bytes=15), [], method="GET"))
    assert sent[0]["status"] == 413
    body = b"".join(item.get("body", b"") for item in sent)
    assert "response_resource_limit" in body.decode()
    assert b"sentinel" not in body and b'"private"' not in body
    assert len([m for m in sent if m["type"] == "http.response.start"]) == 1


def test_normal_json_is_replayed_exactly_and_safe_response_is_whole():
    import asyncio

    async def endpoint(scope, receive, send):
        body = (await receive())["body"]
        assert body == b'{"value":null}'
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})

    sent = asyncio.run(
        exercise(
            HttpBoundary(endpoint),
            [{"type": "http.request", "body": b'{"value":null}', "more_body": False}],
        )
    )
    assert sent[0]["status"] == 200 and json.loads(sent[1]["body"]) == {"value": None}


def test_slow_json_receiver_has_explicit_finite_work_budget():
    import asyncio

    async def exercise_timeout():
        called, sent = [], []

        async def endpoint(scope, receive, send):
            called.append(True)

        async def receive():
            return await asyncio.Future()

        async def send(message):
            sent.append(message)

        await HttpBoundary(endpoint, work_seconds=0.01)(scope(), receive, send)
        assert not called and sent[0]["status"] == 408
        assert "request_receive_timeout" in sent[1]["body"].decode()

    asyncio.run(exercise_timeout())


def test_non_json_original_is_not_subject_to_json_response_limit():
    import asyncio

    async def endpoint(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/pdf")],
            }
        )
        await send({"type": "http.response.body", "body": b"whole PDF", "more_body": False})

    sent = asyncio.run(exercise(HttpBoundary(endpoint, response_bytes=2), [], method="GET"))
    assert sent[0]["status"] == 200 and sent[1]["body"] == b"whole PDF"


def test_host_forwarded_headers_and_security_headers_are_explicit():
    app = create_app(Settings(_env_file=None, database_url=None, allowed_hosts=["testserver"]))
    with TestClient(app) as client:
        valid = client.get(
            "/api/v1/health",
            headers={"X-Forwarded-Host": "attacker.example", "X-Forwarded-Proto": "http"},
        )
        assert valid.status_code == 200
        assert valid.headers["x-frame-options"] == "DENY"
        assert valid.headers["referrer-policy"] == "no-referrer"
        assert valid.headers["x-content-type-options"] == "nosniff"
        assert "frame-ancestors 'none'" in valid.headers["content-security-policy"]
        invalid = client.get("/api/v1/health", headers={"Host": "attacker.example"})
        assert invalid.status_code == 400 and "attacker.example" not in invalid.text
