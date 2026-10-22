"""pilot-logs/1: finite metadata only. Neither message formatting nor exception text."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
PROFILE = json.loads(Path(__file__).with_name("log_profile.json").read_text())
EVENTS = frozenset(
    {
        "request_completed",
        "unhandled_error",
        "proof_transaction_retry",
        "source_store_failure",
        "extraction_completed",
        "financial_evaluation_created",
        "proof_operation_started",
        "proof_operation_failed",
        "proof_operation_completed",
        "operation_failed",
        "readiness_failed",
        "identity_unavailable",
        "identity_rejected",
        "recovery_provenance_unresolved",
    }
)
ENUMS = {
    "method": {"GET", "POST", "HEAD", "OPTIONS"},
    "route": set(PROFILE["routes"]) | {"<unmatched>"},
    "reason_code": set(PROFILE["reasons"]),
    "component": {
        "request",
        "database",
        "storage",
        "source",
        "parser",
        "identity",
        "proof",
        "recovery",
        "readiness",
        "intake",
        "financial",
    },
    "document_type": {"contract", "invoice"},
    "processing_status": {
        "pending",
        "processing",
        "processed",
        "needs_review",
        "needs_ocr",
        "failed",
    },
    "outcome": {"overcharge", "no_overcharge", "undercharge", "blocked"},
    "operation": {
        "generate",
        "export",
        "successor",
        "annotation",
        "review.proposed",
        "review.finalized",
        "disclosure.proposed",
        "disclosure.approved",
    },
    "rule_version": {"core-bundle/1"},
    "parser_version": {"safe-parser/1", "safe-parser/2"},
    "extractor_version": {"explicit-labels/1"},
    "operation_profile": {"proof-operations/1", "recovery-operations/1"},
    "exception_type": {
        "RuntimeError",
        "ValueError",
        "TypeError",
        "DBAPIError",
        "OperationalError",
        "IntegrityError",
        "TimeoutError",
    },
}
IDS = {
    "request_id",
    "organization_id",
    "document_id",
    "extraction_run_id",
    "evaluation_id",
    "evaluation_or_package_id",
}


def opaque_id(value):
    if not isinstance(value, str | UUID):
        return None
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Calling getMessage() or serializing arbitrary extras would expose credentials,
        # exception SQL, document quotations or provider diagnostics under an allowed key.
        event = (
            record.msg
            if isinstance(record.msg, str) and record.msg in EVENTS and not record.args
            else "unclassified_event"
        )
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "profile": PROFILE["profile"],
            "level": logging.getLevelName(record.levelno)
            if record.levelno in {10, 20, 30, 40, 50}
            else "UNKNOWN",
            "logger": "financial_leakage",
            "event": event,
            "request_id": opaque_id(getattr(record, "request_id", request_id_context.get())),
        }
        for name in IDS - {"request_id"}:
            value = opaque_id(getattr(record, name, None))
            if value:
                payload[name] = value
        for name, allowed in ENUMS.items():
            value = getattr(record, name, None)
            if isinstance(value, str) and value in allowed:
                payload[name] = value
        for name, maximum in (
            ("status_code", 599),
            ("duration_ms", 86400000),
            ("source_bytes", 104857600),
        ):
            value = getattr(record, name, None)
            if type(value) is int and 0 <= value <= maximum:
                payload[name] = value
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("financial_leakage")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)


def production_log_config():
    # Uvicorn otherwise re-logs application exception text/tracebacks after the
    # sanitized response. Provider libraries also inherit this safe root handler.
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"safe": {"()": "app.core.logging.JsonFormatter"}},
        "handlers": {"safe": {"class": "logging.StreamHandler", "formatter": "safe"}},
        "root": {"handlers": ["safe"], "level": "WARNING"},
        "loggers": {
            name: {"handlers": ["safe"], "level": "WARNING", "propagate": False}
            for name in (
                "uvicorn",
                "uvicorn.error",
                "uvicorn.access",
                "httpx",
                "httpcore",
                "botocore",
                "sqlalchemy.engine",
                "sqlalchemy.pool",
            )
        },
    }
