import json
import logging
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import JsonFormatter, request_id_context
from app.main import create_app


def test_health_and_request_id():
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "0.1.0"}
        UUID(response.headers["X-Request-ID"])


def test_readiness_without_database_is_honest():
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["message"] == "Database is not configured"


def test_error_envelope_and_supplied_request_id():
    request_id = "09764f14-a488-4d14-a949-0a17faf06186"
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as client:
        response = client.get("/missing", headers={"X-Request-ID": request_id})
        assert response.status_code == 404
        assert response.json()["error"] == {
            "code": "http_404",
            "message": "Not Found",
            "request_id": request_id,
        }


def test_validation_does_not_echo_sensitive_inputs():
    app = create_app(Settings(_env_file=None, database_url=None))

    @app.get("/test-validation")
    def validate(value: int):
        return {"value": value}

    with TestClient(app) as client:
        response = client.get("/test-validation?value=private-document-content")
        assert response.status_code == 422
        assert "private-document-content" not in response.text


def test_unexpected_errors_are_sanitized():
    app = create_app(Settings(_env_file=None, database_url=None))

    @app.get("/test-error")
    def fail():
        raise RuntimeError("private-database-credential")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-error")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"
        assert "private-database-credential" not in response.text
        assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]


def test_cors_allows_only_configured_origin():
    app = create_app(
        Settings(_env_file=None, database_url=None, cors_origins=["http://localhost:3000"])
    )
    with TestClient(app) as client:
        allowed = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
        denied = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "access-control-allow-origin" not in denied.headers


def test_log_is_structured_and_correlated():
    token = request_id_context.set("09764f14-a488-4d14-a949-0a17faf06186")
    try:
        record = logging.LogRecord(
            "financial_leakage", logging.INFO, "", 0, "request_completed", (), None
        )
        record.status_code = 200
        payload = json.loads(JsonFormatter().format(record))
        assert payload["request_id"] == "09764f14-a488-4d14-a949-0a17faf06186"
        assert payload["status_code"] == 200
        assert payload["timestamp"].endswith("+00:00")
    finally:
        request_id_context.reset(token)
