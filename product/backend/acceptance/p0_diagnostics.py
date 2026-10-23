"""Closed, stdlib-only diagnostic protocol for the synthetic seed command.

Never copy child text, exception messages, configuration or identifiers into a
public diagnostic. The legacy fixture JSON remains private subprocess output.
"""

import json
import re

SEED_STAGE = "synthetic_document_identity_fixture"
PHASES = frozenset(
    {
        "parameters",
        "postgres_preflight",
        "alembic",
        "oidc_discovery",
        "fixture_directory",
        "storage_initialization",
        "test_database",
        "synthetic_identities",
        "synthetic_documents",
        "fixture_transaction",
        "fixture_roster",
        "fixture_or_witness",
        "witness",
        "fixture_process",
    }
)
REASONS = {
    "MISSING_TEST_PRECONDITION": ("precondition", {"parameters"}),
    "INVALID_LOOPBACK_CONFIGURATION": ("precondition", {"parameters"}),
    "POSTGRES_VERSION_MISMATCH": ("precondition", {"postgres_preflight"}),
    "POSTGRES_ROLE_REJECTED": ("precondition", {"postgres_preflight"}),
    "ALEMBIC_HEAD_MISMATCH": ("precondition", {"alembic"}),
    "OIDC_DISCOVERY_REJECTED": ("precondition", {"oidc_discovery"}),
    "FIXTURE_DIRECTORY_NOT_FRESH": ("precondition", {"fixture_directory"}),
    "TEST_DATABASE_NOT_EMPTY": ("precondition", {"test_database"}),
    "DATABASE_PREFLIGHT_ERROR": ("dependency", {"postgres_preflight"}),
    "ALEMBIC_PREFLIGHT_ERROR": ("dependency", {"alembic"}),
    "OIDC_DISCOVERY_ERROR": ("dependency", {"oidc_discovery"}),
    "FIXTURE_PERSISTENCE_ERROR": (
        "internal",
        PHASES - {"parameters", "postgres_preflight", "alembic", "oidc_discovery"},
    ),
    "UNEXPECTED_INTERNAL_EXCEPTION": ("internal", PHASES),
    "FIXTURE_INVARIANT_FAILED": ("assertion", PHASES),
    "FIXTURE_PREPARED": ("fixture_only", {"fixture_roster"}),
    "DIAGNOSTIC_UNAVAILABLE": ("protocol", {"fixture_process"}),
    "FIXTURE_PROTOCOL_MISMATCH": ("protocol", {"fixture_process"}),
    "FIXTURE_PROCESS_TIMEOUT": ("process", {"fixture_process"}),
    "FIXTURE_PROCESS_INTERRUPTED": ("process", {"fixture_process"}),
    "FIXTURE_PROCESS_UNAVAILABLE": ("process", {"fixture_process"}),
}
LEGACY_MISSING = {
    "dedicated_loopback_database_and_test_issuer_configuration": (
        "INVALID_LOOPBACK_CONFIGURATION",
        "parameters",
    ),
    "PostgreSQL_17": ("POSTGRES_VERSION_MISMATCH", "postgres_preflight"),
    "non_privileged_fixture_role": ("POSTGRES_ROLE_REJECTED", "postgres_preflight"),
    "existing_migrations_at_head": ("ALEMBIC_HEAD_MISMATCH", "alembic"),
    "test_OIDC_discovery_PKCE_RS256": ("OIDC_DISCOVERY_REJECTED", "oidc_discovery"),
    "fresh_disposable_fixture_directory": ("FIXTURE_DIRECTORY_NOT_FRESH", "fixture_directory"),
    "empty_dedicated_test_database": ("TEST_DATABASE_NOT_EMPTY", "test_database"),
    "database_or_test_issuer_preflight": ("DIAGNOSTIC_UNAVAILABLE", "fixture_process"),
    "fixture_or_witness_verification_failed": (
        "UNEXPECTED_INTERNAL_EXCEPTION",
        "fixture_or_witness",
    ),
}
MISSING_NAMES = frozenset(LEGACY_MISSING) | {
    "FLA_DATABASE_URL",
    "OIDC_ISSUER_URL",
    "PRODUCT_OWNER_SUBJECT",
    "PRODUCT_ANALYST_SUBJECT",
    "explicit_synthetic_development_authorization",
}

# D2 is an optional, closed extension. D1 receipts retain their exact shape.
D2_SUBSTAGES = {
    "postgres_preflight": {"database_connect"},
    "alembic": {"migration_check"},
    "oidc_discovery": {"discovery_fetch"},
    "fixture_directory": {"directory_check"},
    "storage_initialization": {"storage_initialize"},
    "test_database": {"empty_database_check"},
    "synthetic_identities": {
        "users_insert",
        "users_flush",
        "operator_context",
        "organizations_insert",
        "organizations_flush",
        "oidc_identities_insert",
        "oidc_identities_flush",
        "memberships_insert",
        "memberships_flush",
    },
    "synthetic_documents": {"documents_prepare", "documents_flush"},
    "fixture_transaction": {"audit_verify", "transaction_commit"},
    "fixture_roster": {"roster_write"},
    "fixture_or_witness": {"entrypoint"},
}
D2_EXCEPTION_CATEGORIES = frozenset(
    {
        "sqlalchemy_integrity",
        "sqlalchemy_database",
        "sqlalchemy_orm",
        "postgresql",
        "operator_rejected",
        "assertion",
        "filesystem",
        "timeout",
        "unexpected",
    }
)


def validate_d2(value, *, reason_code, phase, fixture_status):
    keys = {
        "schema_version",
        "stage",
        "substage",
        "fixture_status",
        "reason_code",
        "exception_category",
        "sqlstate",
        "e2e_executed",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Invalid D2 diagnostic")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 2
        or value["stage"] != SEED_STAGE
        or not isinstance(value["substage"], str)
        or value["substage"] not in D2_SUBSTAGES.get(phase, set())
        or value["fixture_status"] != fixture_status
        or fixture_status not in {"BLOCKED", "FAIL"}
        or value["reason_code"] != reason_code
        or not isinstance(value["exception_category"], str)
        or value["exception_category"] not in D2_EXCEPTION_CATEGORIES
        or value["e2e_executed"] is not False
        or not (
            value["sqlstate"] is None
            or isinstance(value["sqlstate"], str)
            and re.fullmatch(r"[0-9A-Z]{5}", value["sqlstate"]) is not None
            and value["sqlstate"] != "00000"
        )
        or value["sqlstate"] is not None
        and value["exception_category"]
        not in {
            "sqlalchemy_integrity",
            "sqlalchemy_database",
            "sqlalchemy_orm",
            "postgresql",
        }
        or reason_code == "FIXTURE_INVARIANT_FAILED"
        and value["exception_category"] != "assertion"
    ):
        raise ValueError("Invalid D2 diagnostic")


def detail(reason_code, phase):
    """Producer-side constants only; reject accidental arbitrary text."""
    if reason_code not in REASONS or phase not in REASONS[reason_code][1]:
        raise ValueError("Invalid fixture diagnostic constant")
    return {"reason_code": reason_code, "phase": phase}


def public_diagnostic(exit_code, fixture_status, reason_code, phase, *, diagnostic_d2=None):
    value = {
        "schema_version": 1,
        "stage": SEED_STAGE,
        "exit_code": exit_code,
        "fixture_status": fixture_status,
        **detail(reason_code, phase),
        "category": REASONS[reason_code][0],
        "e2e_executed": False,
    }
    if diagnostic_d2 is not None:
        value["diagnostic_d2"] = diagnostic_d2
    validate_diagnostic(value)
    return value


def validate_diagnostic(value):
    keys = {
        "schema_version",
        "stage",
        "exit_code",
        "fixture_status",
        "reason_code",
        "phase",
        "category",
        "e2e_executed",
    }
    if not isinstance(value, dict) or set(value) not in (keys, keys | {"diagnostic_d2"}):
        raise ValueError("Invalid public fixture diagnostic")
    code, phase = value["reason_code"], value["phase"]
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["stage"] != SEED_STAGE
        or not (
            value["exit_code"] is None
            or type(value["exit_code"]) is int
            and -128 <= value["exit_code"] <= 255
        )
        or value["fixture_status"] not in ("FIXTURE_ONLY", "BLOCKED", "FAIL", "UNAVAILABLE")
        or not isinstance(code, str)
        or code not in REASONS
        or not isinstance(phase, str)
        or phase not in REASONS[code][1]
        or value["category"] != REASONS[code][0]
        or value["e2e_executed"] is not False
    ):
        raise ValueError("Invalid public fixture diagnostic")
    category, exit_code, status = value["category"], value["exit_code"], value["fixture_status"]
    if (
        category == "fixture_only"
        and (exit_code != 0 or status != "FIXTURE_ONLY")
        or category in {"precondition", "dependency", "internal"}
        and (exit_code != 2 or status != "BLOCKED")
        or category == "assertion"
        and (exit_code != 1 or status != "FAIL")
        or category == "process"
        and (
            status != "UNAVAILABLE"
            or (
                exit_code is not None
                if code != "FIXTURE_PROCESS_INTERRUPTED"
                else exit_code is None or exit_code >= 0
            )
        )
    ):
        raise ValueError("Contradictory public fixture diagnostic")
    if "diagnostic_d2" in value:
        validate_d2(value["diagnostic_d2"], reason_code=code, phase=phase, fixture_status=status)


def validate_result_diagnostic(value):
    if "fixture_diagnostic" not in value:
        return  # Existing evidence without the D1 extension keeps its contract.
    diagnostic = value["fixture_diagnostic"]
    validate_diagnostic(diagnostic)
    if diagnostic["reason_code"] != "FIXTURE_PREPARED" and (
        value.get("status") not in ("BLOCKED", "FAIL") or value.get("e2e_executed") is not False
    ):
        raise ValueError("Unsuccessful fixture cannot certify E2E")


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def seed_outcome(exit_code, stdout=b"", *, timeout=False, unavailable=False):
    """Return (wrapper status, public diagnostic), never child output.

    Missing/invalid/contradictory protocol is FAIL, not evidence of a specific
    SQL/OIDC failure. A documented code 2 + BLOCKED remains BLOCKED.
    """

    def result(status, code, phase="fixture_process", observed="UNAVAILABLE", diagnostic_d2=None):
        return status, public_diagnostic(
            exit_code, observed, code, phase, diagnostic_d2=diagnostic_d2
        )

    if timeout:
        return result("BLOCKED", "FIXTURE_PROCESS_TIMEOUT")
    if unavailable:
        return result("BLOCKED", "FIXTURE_PROCESS_UNAVAILABLE")
    if type(exit_code) is not int or not -128 <= exit_code <= 255:
        # Do not publish an unbounded or non-numeric alleged process code.
        exit_code = None
        return result("FAIL", "FIXTURE_PROTOCOL_MISMATCH")
    if exit_code < 0:
        return result("BLOCKED", "FIXTURE_PROCESS_INTERRUPTED")
    if exit_code not in (0, 1, 2):
        return result("FAIL", "FIXTURE_PROTOCOL_MISMATCH")
    try:
        if not isinstance(stdout, bytes) or not 0 < len(stdout) <= 16384:
            raise ValueError()
        value = json.loads(stdout, object_pairs_hook=_unique)
        if not isinstance(value, dict) or set(value) - {
            "status",
            "missing",
            "check",
            "e2e",
            "diagnostic",
            "roster",
            "financial_records_inserted",
            "diagnostic_d2",
        }:
            raise ValueError()
        status = value.get("status")
        if status not in ("FIXTURE_ONLY", "BLOCKED", "FAIL"):
            raise ValueError()
        if value.get("e2e") != "NOT_EXECUTED":
            raise ValueError()
        shapes = {
            "FIXTURE_ONLY": {"status", "e2e", "financial_records_inserted", "roster"},
            "BLOCKED": {"status", "e2e", "missing", "diagnostic"},
            "FAIL": {"status", "e2e", "check", "diagnostic"},
        }
        shapes["BLOCKED"].add("diagnostic_d2")
        shapes["FAIL"].add("diagnostic_d2")
        if set(value) - shapes[status]:
            raise ValueError()
        if status == "BLOCKED" and not value.get("missing"):
            raise ValueError()
        if status == "FAIL" and value.get("check") != "persisted_financial_invariants":
            raise ValueError()
        if "missing" in value and (
            not isinstance(value["missing"], list)
            or not value["missing"]
            or len(value["missing"]) > len(MISSING_NAMES)
            or any(not isinstance(n, str) or n not in MISSING_NAMES for n in value["missing"])
        ):
            raise ValueError()
        if "check" in value and value["check"] != "persisted_financial_invariants":
            raise ValueError()
        if "roster" in value and (
            not isinstance(value["roster"], str) or len(value["roster"]) > 4096
        ):
            raise ValueError()
        if "financial_records_inserted" in value and (
            type(value["financial_records_inserted"]) is not int
            or value["financial_records_inserted"] != 0
        ):
            raise ValueError()
        if status == "FIXTURE_ONLY" and (
            value.get("financial_records_inserted") != 0
            or type(value.get("financial_records_inserted")) is not int
            or not value.get("roster")
            or "missing" in value
            or "check" in value
        ):
            raise ValueError()
        if "diagnostic" in value:
            d = value["diagnostic"]
            if not isinstance(d, dict) or set(d) != {"reason_code", "phase"}:
                raise ValueError()
            code, phase = d["reason_code"], d["phase"]
            if not isinstance(code, str) or not isinstance(phase, str):
                raise ValueError()
            detail(code, phase)
            if REASONS[code][0] in {"process", "protocol", "fixture_only"}:
                raise ValueError()  # Only the parent can observe process failures.
            if status == "FAIL" and code != "FIXTURE_INVARIANT_FAILED":
                raise ValueError()
            if status == "BLOCKED":
                missing = value["missing"]
                if missing == ["database_or_test_issuer_preflight"]:
                    if code not in {
                        "DATABASE_PREFLIGHT_ERROR",
                        "ALEMBIC_PREFLIGHT_ERROR",
                        "OIDC_DISCOVERY_ERROR",
                    }:
                        raise ValueError()
                elif missing == ["fixture_or_witness_verification_failed"]:
                    if code not in {
                        "DATABASE_PREFLIGHT_ERROR",
                        "FIXTURE_PERSISTENCE_ERROR",
                        "UNEXPECTED_INTERNAL_EXCEPTION",
                    }:
                        raise ValueError()
                elif len(missing) == 1 and missing[0] in LEGACY_MISSING:
                    if (code, phase) != LEGACY_MISSING[missing[0]]:
                        raise ValueError()
                elif code != "MISSING_TEST_PRECONDITION" or any(
                    item in LEGACY_MISSING for item in missing
                ):
                    raise ValueError()
        elif status == "FIXTURE_ONLY":
            code, phase = "FIXTURE_PREPARED", "fixture_roster"
        elif status == "FAIL":
            code, phase = "FIXTURE_INVARIANT_FAILED", "fixture_or_witness"
        else:
            missing = value.get("missing", [])
            if len(missing) == 1 and missing[0] in LEGACY_MISSING:
                code, phase = LEGACY_MISSING[missing[0]]
            elif missing and all(n not in LEGACY_MISSING for n in missing):
                code, phase = "MISSING_TEST_PRECONDITION", "parameters"
            else:
                code, phase = "DIAGNOSTIC_UNAVAILABLE", "fixture_process"
        extension = value.get("diagnostic_d2")
        if "diagnostic_d2" in value:
            validate_d2(extension, reason_code=code, phase=phase, fixture_status=status)
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        return result("FAIL", "DIAGNOSTIC_UNAVAILABLE")
    if {0: "FIXTURE_ONLY", 1: "FAIL", 2: "BLOCKED"}[exit_code] != status or (
        (code == "FIXTURE_PREPARED") != (status == "FIXTURE_ONLY")
        or (status == "FAIL" and REASONS[code][0] not in {"assertion", "internal"})
        or (status == "BLOCKED" and REASONS[code][0] == "assertion")
    ):
        return result("FAIL", "FIXTURE_PROTOCOL_MISMATCH", observed=status)
    return result(status, code, phase, status, extension)
