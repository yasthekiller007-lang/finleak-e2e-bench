"""Synthetic protocol/adversarial tests. No PostgreSQL, Actions or OIDC login."""

import base64
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import emit_evidence
import pytest
import runtime
from acceptance.p0_diagnostics import (
    LEGACY_MISSING,
    SEED_STAGE,
    public_diagnostic,
    seed_outcome,
    validate_diagnostic,
    validate_result_diagnostic,
)
from gate import DIAGNOSTIC_SOURCE_OVERLAY, Blocked, verify_source

CANARY = "synthetic-secret-value-DO-NOT-PUBLISH"


def payload(status="BLOCKED", **extra):
    value = {"status": status, "e2e": "NOT_EXECUTED", **extra}
    if status == "FIXTURE_ONLY":
        value.update(financial_records_inserted=0, roster="/private/synthetic/roster.json")
    if status == "FAIL":
        value.setdefault("check", "persisted_financial_invariants")
    return json.dumps(value).encode()


@pytest.mark.parametrize(
    "code,body,status,reason",
    [
        (0, payload("FIXTURE_ONLY"), "FIXTURE_ONLY", "FIXTURE_PREPARED"),
        (2, payload(missing=["PostgreSQL_17"]), "BLOCKED", "POSTGRES_VERSION_MISMATCH"),
        (
            1,
            payload("FAIL", check="persisted_financial_invariants"),
            "FAIL",
            "FIXTURE_INVARIANT_FAILED",
        ),
        (
            2,
            payload(missing=["fixture_or_witness_verification_failed"]),
            "BLOCKED",
            "UNEXPECTED_INTERNAL_EXCEPTION",
        ),
        (2, payload(missing=["FLA_DATABASE_URL"]), "BLOCKED", "MISSING_TEST_PRECONDITION"),
        (
            2,
            payload(missing=["database_or_test_issuer_preflight"]),
            "BLOCKED",
            "DIAGNOSTIC_UNAVAILABLE",
        ),
        (3, payload("FIXTURE_ONLY"), "FAIL", "FIXTURE_PROTOCOL_MISMATCH"),
        (-15, b"", "BLOCKED", "FIXTURE_PROCESS_INTERRUPTED"),
        (0, b"", "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (2, b"not json", "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (0, b"[]", "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (0, b'{"status":"PASS"}', "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (0, payload("PREFLIGHT_ONLY"), "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (0, b"\xff", "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (0, b"[" * 2000 + b"]" * 2000, "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (0, b"x" * 16385, "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (0, b'{"status":"BLOCKED","status":"FIXTURE_ONLY"}', "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (0, payload("FIXTURE_ONLY", extra=CANARY), "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
        (2, payload(missing=[CANARY]), "FAIL", "DIAGNOSTIC_UNAVAILABLE"),
    ],
)
def test_bounded_fixture_protocol(code, body, status, reason):
    actual, diagnostic = seed_outcome(code, body)
    assert actual == status and diagnostic["reason_code"] == reason
    assert diagnostic["exit_code"] == code and diagnostic["stage"] == SEED_STAGE
    assert diagnostic["e2e_executed"] is False
    assert CANARY not in json.dumps(diagnostic)
    validate_diagnostic(diagnostic)


@pytest.mark.parametrize(
    "code,status",
    [
        (0, "BLOCKED"),
        (0, "FAIL"),
        (1, "FIXTURE_ONLY"),
        (2, "FAIL"),
        (1, "BLOCKED"),
        (2, "FIXTURE_ONLY"),
    ],
)
def test_exit_status_contradictions_fail_closed(code, status):
    body = payload(status, missing=["PostgreSQL_17"]) if status == "BLOCKED" else payload(status)
    outcome, diagnostic = seed_outcome(code, body)
    assert outcome == "FAIL" and diagnostic["reason_code"] == "FIXTURE_PROTOCOL_MISMATCH"
    assert diagnostic["fixture_status"] == status


@pytest.mark.parametrize("name", list(LEGACY_MISSING))
def test_legacy_known_missing_reasons_are_closed_and_observable(name):
    outcome, diagnostic = seed_outcome(2, payload(missing=[name]))
    assert outcome == "BLOCKED" and diagnostic["reason_code"] == LEGACY_MISSING[name][0]


@pytest.mark.parametrize(
    "keyword,reason",
    [("timeout", "FIXTURE_PROCESS_TIMEOUT"), ("unavailable", "FIXTURE_PROCESS_UNAVAILABLE")],
)
def test_no_response_is_not_pass(keyword, reason):
    status, diagnostic = seed_outcome(None, CANARY.encode(), **{keyword: True})
    assert status == "BLOCKED" and diagnostic["reason_code"] == reason
    assert diagnostic["exit_code"] is None and CANARY not in json.dumps(diagnostic)


@pytest.mark.parametrize("code", [None, True, "2", 256, -129])
def test_unreliable_exit_codes_are_not_published_as_process_evidence(code):
    status, diagnostic = seed_outcome(code, payload())
    assert status == "FAIL" and diagnostic["exit_code"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"stdout": CANARY},
        {"reason_code": CANARY},
        {"phase": CANARY},
        {"phase": "alembic"},
        {"e2e_executed": True},
        {"exit_code": True},
        {"exit_code": 0},
        {"exit_code": None},
        {"fixture_status": "FIXTURE_ONLY"},
        {"fixture_status": "PASS"},
        {"schema_version": True},
        {"category": CANARY},
    ],
)
def test_public_schema_rejects_extra_or_free_text_fields(change):
    diagnostic = public_diagnostic(2, "BLOCKED", "POSTGRES_ROLE_REJECTED", "postgres_preflight")
    diagnostic.update(change)
    with pytest.raises((ValueError, TypeError)):
        validate_diagnostic(diagnostic)


@pytest.mark.parametrize(
    "diagnostic",
    [
        {"reason_code": CANARY, "phase": "alembic"},
        {"reason_code": "POSTGRES_ROLE_REJECTED", "phase": "alembic"},
        {
            "reason_code": "POSTGRES_ROLE_REJECTED",
            "phase": "postgres_preflight",
            "exception": CANARY,
        },
        {"reason_code": [CANARY], "phase": "alembic"},
        {"reason_code": "FIXTURE_PREPARED", "phase": "fixture_roster"},
    ],
)
def test_untrusted_structured_child_diagnostic_cannot_leak(diagnostic):
    status, public = seed_outcome(
        2, payload(missing=["fixture_or_witness_verification_failed"], diagnostic=diagnostic)
    )
    assert status == "FAIL" and CANARY not in json.dumps(public)


def test_private_roster_and_raw_stderr_are_not_part_of_public_diagnostic():
    raw = payload("FIXTURE_ONLY").replace(b"/private/synthetic/roster.json", CANARY.encode())
    status, diagnostic = seed_outcome(0, raw)
    assert status == "FIXTURE_ONLY" and CANARY not in json.dumps(diagnostic)
    assert set(diagnostic) == {
        "schema_version",
        "stage",
        "exit_code",
        "fixture_status",
        "reason_code",
        "phase",
        "category",
        "e2e_executed",
    }


@pytest.mark.parametrize(
    "body",
    [
        b'{"status":"FAIL","e2e":"NOT_EXECUTED"}',
        payload(),
        payload(
            missing=["PostgreSQL_17"],
            diagnostic={
                "reason_code": "POSTGRES_ROLE_REJECTED",
                "phase": "postgres_preflight",
            },
        ),
        payload(
            missing=["fixture_or_witness_verification_failed"],
            diagnostic={
                "reason_code": "FIXTURE_PROCESS_TIMEOUT",
                "phase": "fixture_process",
            },
        ),
        payload("BLOCKED", missing=["PostgreSQL_17"], roster=CANARY),
    ],
)
def test_missing_or_contradictory_reason_is_not_invented(body):
    status, diagnostic = seed_outcome(1 if b'"FAIL"' in body else 2, body)
    assert status == "FAIL" and diagnostic["reason_code"] == "DIAGNOSTIC_UNAVAILABLE"
    assert CANARY not in json.dumps(diagnostic)


@pytest.mark.parametrize(
    "status,executed", [("PASS", False), ("PASS", True), ("FAIL", True), ("BLOCKED", True)]
)
def test_diagnostic_cannot_certify_an_unexecuted_or_unsuccessful_e2e(status, executed):
    with pytest.raises(ValueError):
        validate_result_diagnostic(
            {
                "status": status,
                "e2e_executed": executed,
                "fixture_diagnostic": public_diagnostic(
                    2, "BLOCKED", "POSTGRES_ROLE_REJECTED", "postgres_preflight"
                ),
            }
        )


def test_safe_evidence_is_hash_verifiable(tmp_path, capsys):
    diagnostic = seed_outcome(2, payload(missing=["non_privileged_fixture_role"]))[1]
    result = {"status": "BLOCKED", "e2e_executed": False, "fixture_diagnostic": diagnostic}
    raw = (json.dumps(result) + "\n").encode()
    (tmp_path / "result.json").write_bytes(raw)
    emit_evidence.emit(tmp_path)
    lines = capsys.readouterr().out.splitlines()
    receipt = json.loads(lines[0].split(" ", 1)[1])
    assert base64.b64decode(receipt["base64"]) == raw
    assert receipt["sha256"] == hashlib.sha256(raw).hexdigest()
    assert json.loads(lines[1].split(" ", 1)[1]) == [
        {"file": "result.json", "sha256": receipt["sha256"]}
    ]


def test_emitter_schema_rejects_unrecognizable_secret_without_echoing_it(tmp_path, capsys):
    # Does not contain any of the historical forbidden words.
    diagnostic = seed_outcome(2, payload(missing=["non_privileged_fixture_role"]))[1]
    diagnostic["unexpected"] = CANARY
    (tmp_path / "result.json").write_text(json.dumps({"fixture_diagnostic": diagnostic}))
    with pytest.raises(SystemExit, match="diagnostic schema guard"):
        emit_evidence.emit(tmp_path)
    assert capsys.readouterr().out == ""


def test_emitter_preserves_bootstrap_blocked_receipt(tmp_path, capsys):
    emit_evidence.emit(tmp_path)
    value = json.loads((tmp_path / "result.json").read_text())
    assert value["status"] == "BLOCKED" and value["e2e_executed"] is False
    assert "FINLEAK_P0_MANIFEST " in capsys.readouterr().out


@pytest.mark.parametrize("raw", [b"x" * 32769, b'{"access_token":"synthetic"}'])
def test_emitter_preserves_legacy_size_and_word_guards(tmp_path, capsys, raw):
    (tmp_path / "result.json").write_bytes(raw)
    with pytest.raises(SystemExit):
        emit_evidence.emit(tmp_path)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "private",
    [
        "Bearer synthetic-access-credential",
        "synthetic.id.signature",
        "postgresql://synthetic:private@localhost/example",
        "-----BEGIN PRIVATE KEY-----",
        "session=synthetic-cookie",
        "synthetic-authorization-code",
        "SQL parameters: synthetic-customer-value",
        "https://issuer.invalid/private-response",
    ],
)
def test_arbitrary_private_child_fields_never_reach_decoded_receipts(private):
    status, diagnostic = seed_outcome(
        2,
        payload(
            missing=["fixture_or_witness_verification_failed"],
            private_output=private,
        ),
    )
    assert status == "FAIL"
    raw = json.dumps(diagnostic).encode()
    receipt = base64.b64encode(raw)
    assert private.encode() not in base64.b64decode(receipt)


def test_frozen_manifest_and_exact_fixture_overlay_are_both_verified(tmp_path):
    root = Path(__file__).resolve().parents[3]
    verify_source(root)
    target = "backend/acceptance/product_v11.py"
    baseline, candidate = DIAGNOSTIC_SOURCE_OVERLAY[target]
    assert baseline != candidate and len(candidate) == 64
    (tmp_path / "bench/p0").mkdir(parents=True)
    (tmp_path / "backend/acceptance").mkdir(parents=True)
    (tmp_path / target).write_bytes((root / target).read_bytes())
    manifest = tmp_path / "bench/p0/v23-source.sha256"
    manifest.write_text(baseline + "  " + target + "\n")
    verify_source(tmp_path)
    manifest.write_text("0" * 64 + "  " + target + "\n")
    with pytest.raises(Blocked):
        verify_source(tmp_path)
    manifest.write_text(baseline + "  " + target + "\n")
    (tmp_path / target).write_text("arbitrary changed fixture")
    with pytest.raises(Blocked):
        verify_source(tmp_path)


@pytest.mark.parametrize(
    "mode,expected,reason",
    [
        ("blocked", 2, "POSTGRES_ROLE_REJECTED"),
        ("assertion", 1, "FIXTURE_INVARIANT_FAILED"),
        ("timeout", 2, "FIXTURE_PROCESS_TIMEOUT"),
        ("spawn", 2, "FIXTURE_PROCESS_UNAVAILABLE"),
        ("malformed", 1, "DIAGNOSTIC_UNAVAILABLE"),
    ],
)
@pytest.mark.parametrize("cleanup_error", [False, True])
def test_executor_preserves_partial_steps_and_cleanup_with_explicit_doubles(
    monkeypatch, tmp_path, capsys, mode, expected, reason, cleanup_error
):
    """Exercise the real orchestration branches with zero external services."""
    (tmp_path / "frontend/node_modules/playwright-core").mkdir(parents=True)
    catalog = tmp_path / "frontend/node_modules/playwright-core/browsers.json"
    catalog.write_text("synthetic browser catalog")
    cache = tmp_path / "browser-cache"
    cache.mkdir()
    (cache / "chrome-headless-shell").write_bytes(b"synthetic browser, never executed")
    (tmp_path / "bench/p0").mkdir(parents=True)
    pins = {
        "playwright_browsers_json_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "postgres": {"config_digest": "synthetic-image-id"},
    }
    (tmp_path / "bench/p0/pins.json").write_text(json.dumps(pins))
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    monkeypatch.setattr(runtime, "PRIVATE", tmp_path / "private")
    monkeypatch.setattr(runtime, "EVIDENCE", tmp_path / "evidence")
    monkeypatch.setattr(runtime, "execution_gate", lambda _root: None)
    monkeypatch.setattr(runtime, "resources", lambda _root: {"explicit_test_double": True})
    monkeypatch.setattr(runtime.platform, "python_version", lambda: "3.12.15")
    monkeypatch.setattr(runtime, "ready", lambda *_args: None)
    monkeypatch.setattr(
        runtime.shutil, "disk_usage", lambda _root: SimpleNamespace(free=8 * 1024**3)
    )
    for key in (
        "GITHUB_EVENT_NAME",
        "GITHUB_ACTOR",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_SHA",
        "GITHUB_REPOSITORY",
        "P0_RUNNER_KIND",
        "P0_AUTHORIZATION",
        "P0_EXPECTED_COMMIT",
        "P0_BILLING_SHA256",
    ):
        monkeypatch.setenv(key, "explicit-unit-test-double")
    monkeypatch.setenv("P0_JOB_STARTED_EPOCH", str(runtime.time.time()))
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(cache))
    process = SimpleNamespace(pid=123456, poll=lambda: None, wait=lambda: None)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_args, **_kwargs: process)
    calls = []

    def command(args, **kwargs):
        calls.append(args)
        if args[:2] == ["node", "--version"]:
            out = b"v24.21.0\n"
        elif args[:2] == ["uv", "--version"]:
            out = b"uv 0.12.19\n"
        elif args[:3] == ["docker", "image", "inspect"]:
            out = json.dumps(
                [{"Architecture": "amd64", "Os": "linux", "Id": "synthetic-image-id"}]
            ).encode()
        elif args[-3:] == ["-m", "acceptance.product_v11", "seed"]:
            if mode == "timeout":
                raise subprocess.TimeoutExpired(
                    args, 20, output=CANARY.encode(), stderr=CANARY.encode()
                )
            if mode == "spawn":
                raise OSError(CANARY)
            out = (
                payload(missing=["non_privileged_fixture_role"])
                if mode == "blocked"
                else payload("FAIL", check="persisted_financial_invariants")
                if mode == "assertion"
                else CANARY.encode()
            )
            return SimpleNamespace(
                returncode=2 if mode == "blocked" else 1, stdout=out, stderr=CANARY.encode()
            )
        else:
            out = b"28.0.4\n"
        return SimpleNamespace(returncode=0, stdout=out, stderr=b"")

    monkeypatch.setattr(runtime.subprocess, "run", command)
    cleaned = []

    def cleanup():
        cleaned.append(True)
        if cleanup_error:
            raise OSError(CANARY)

    monkeypatch.setattr(runtime, "cleanup", cleanup)
    assert runtime.execute() == (1 if cleanup_error else expected)
    result = json.loads((tmp_path / "evidence/result.json").read_text())
    assert result["fixture_diagnostic"]["reason_code"] == reason
    assert result["migration_0010"] == "APPLIED_SYNTHETIC_DATABASE_ONLY"
    assert result["steps"][-1]["stage"] == SEED_STAGE
    assert result["cleanup"] == ("FAILED_OR_INTERRUPTED" if cleanup_error else "COMPLETED")
    assert cleaned == [True]
    assert not result["e2e_executed"] and result["status"] != "PASS"
    assert sum(args[-3:] == ["-m", "acceptance.product_v11", "seed"] for args in calls) == 1
    output = capsys.readouterr().out
    assert CANARY not in json.dumps(result) and CANARY not in output
    encoded = next(
        line.split("=", 1)[1]
        for line in output.splitlines()
        if line.startswith("FINLEAK_P0_RESULT_BASE64=")
    )
    assert CANARY.encode() not in base64.b64decode(encoded)
