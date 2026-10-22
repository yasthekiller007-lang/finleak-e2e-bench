import json
import logging
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import ENUMS, IDS, JsonFormatter
from app.main import create_app

CANARY = 'Bearer private-token; cookie=secret; bank=FR123456789; "customer quotation"'


@pytest.mark.parametrize(
    "field",
    sorted(
        set(ENUMS)
        | IDS
        | {
            "duration_ms",
            "source_bytes",
            "status_code",
            "authorization",
            "cookie",
            "filename",
            "amount",
            "message",
        }
    ),
)
def test_arbitrary_data_never_becomes_allowlisted_log_metadata(field):
    record = logging.LogRecord(
        CANARY,
        logging.ERROR,
        CANARY,
        0,
        "request_completed",
        (),
        (RuntimeError, RuntimeError(CANARY), None),
    )
    setattr(record, field, CANARY)
    formatted = JsonFormatter().format(record)
    assert CANARY not in formatted and "private-token" not in formatted
    assert len(formatted) < 500


def test_log_message_format_args_and_exception_text_are_not_rendered():
    for message, args in (
        (CANARY, ()),
        ("request_completed %s", (CANARY,)),
        ("request_completed", (CANARY,)),
    ):
        record = logging.LogRecord(CANARY, logging.WARNING, "", 0, message, args, None)
        assert json.loads(JsonFormatter().format(record))["event"] == "unclassified_event"
        assert CANARY not in JsonFormatter().format(record)
    record = logging.LogRecord(
        "financial_leakage", logging.WARNING, "", 0, "proof_operation_failed", (), None
    )
    record.reason_code = "proof_snapshot_integrity"
    record.organization_id = str(uuid4())
    record.duration_ms = 15
    payload = json.loads(JsonFormatter().format(record))
    assert payload["reason_code"] == "proof_snapshot_integrity"
    assert payload["organization_id"] == record.organization_id and payload["duration_ms"] == 15


def test_actual_error_logs_and_envelope_do_not_echo_body_or_unmatched_route(caplog):
    app = create_app(Settings(_env_file=None, database_url=None))
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(JsonFormatter().format(record))

    logger = logging.getLogger("financial_leakage")
    capture = Capture()
    logger.addHandler(capture)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/unknown/private-token",
                content=CANARY,
                headers={"X-Request-ID": CANARY, "Authorization": CANARY, "Cookie": CANARY},
            )
            assert response.status_code == 404
            assert "private-token" not in response.text
        output = "\n".join(records)
        assert "private-token" not in output and CANARY not in output
        assert "request_completed" in output and "operation_failed" in output
    finally:
        logger.removeHandler(capture)


def test_actual_runtime_and_provider_handlers_suppress_reraised_exception_text():
    import subprocess
    import sys

    script = """import logging, logging.config
from app.core.logging import production_log_config
logging.config.dictConfig(production_log_config())
for name in ('uvicorn.error','httpx','botocore','sqlalchemy.engine','arbitrary.provider'):
 try: raise RuntimeError('private-token bank-account customer-source')
 except RuntimeError: logging.getLogger(name).exception('provider request %s', 'private-token')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        check=True,
        timeout=10,
    )
    output = result.stderr.decode()
    assert "private-token" not in output and "bank-account" not in output
    assert "Traceback" not in output
    assert output.count('"event": "unclassified_event"') == 5
