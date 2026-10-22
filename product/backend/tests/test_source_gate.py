"""Explicit operational availability without automatic upstream financial authority."""

import hashlib
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.db.models import Document, ExtractionRun
from app.financial.models import FinancialEvaluation, FinancialRevision
from app.modules.scanner import ScanVerdict
from app.operations.source_models import PilotSourceRelease, PilotSourceRequest, PilotSourceScan
from app.proof.models import ProofPackage
from app.recovery.models import RecoveryRecord
from tests.test_documents import CSV, headers, path, upload
from tests.test_documents import api as api
from tests.test_financial_api import set_role

pytestmark = pytest.mark.integration


def source_post(api, document, action, data=None, subject="a", org="a", key=None):
    return api["client"].post(
        path(api, org) + f"/{document}/{action}",
        json=data or {"reason": "Explicit synthetic operational source action"},
        headers={**headers(api, subject), "Idempotency-Key": str(key or uuid4())},
    )


def status(api, document):
    response = api["client"].get(path(api) + f"/{document}/source-status", headers=headers(api))
    assert response.status_code == 200, response.text
    return response.json()


def test_upload_is_private_unscanned_until_explicit_clean_scan_and_owner_release(api):
    response = upload(api, release=False)
    document = response.json()["id"]
    assert status(api, document)["state"] == "UNSCANNED"
    assert (
        api["client"].get(path(api) + f"/{document}/content", headers=headers(api)).status_code
        == 409
    )
    assert source_post(api, document, "process").status_code == 409
    assert api["session"].scalar(select(func.count()).select_from(ExtractionRun)) == 0
    scanned = source_post(api, document, "scan")
    assert scanned.status_code == 200, scanned.text
    scan = scanned.json()["scan_id"]
    assert status(api, document)["state"] == "CLEAN_AWAITING_RELEASE"
    denied = source_post(
        api, document, "release", {"scan_id": scan, "reason": "Analyst cannot release"}
    )
    assert denied.status_code == 403
    assert (
        source_post(
            api,
            document,
            "release",
            {"scan_id": scan, "reason": "Viewer cannot release"},
            subject="viewer",
        ).status_code
        == 403
    )
    set_role(api, "owner")
    released = source_post(
        api, document, "release", {"scan_id": scan, "reason": "Explicit controlled release"}
    )
    assert released.status_code == 200, released.text
    assert status(api, document)["state"] == "RELEASED"
    content = api["client"].get(path(api) + f"/{document}/content", headers=headers(api))
    assert content.status_code == 200 and content.content == CSV
    stored = api["session"].get(Document, UUID(document))
    assert stored.sha256 == hashlib.sha256(CSV).hexdigest()
    for model in (
        ExtractionRun,
        FinancialEvaluation,
        FinancialRevision,
        ProofPackage,
        RecoveryRecord,
    ):
        assert api["session"].scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("verdict", ["INFECTED", "SUSPICIOUS", "UNKNOWN", "TIMEOUT", "UNAVAILABLE"])
def test_nonclean_scan_blocks_process_download_and_release_without_source_transform(api, verdict):
    document = upload(api, release=False).json()["id"]

    class ClosedScanner:
        def scan(self, *args, **kwargs):
            return ScanVerdict(verdict, version="clamav/1.4.6;database/28000")

    api["app"].state.scanner = ClosedScanner()
    scanned = source_post(api, document, "scan")
    assert scanned.status_code == 200, scanned.text
    assert status(api, document)["state"] == verdict
    assert source_post(api, document, "process").status_code == 409
    assert (
        api["client"].get(path(api) + f"/{document}/content", headers=headers(api)).status_code
        == 409
    )
    set_role(api, "owner")
    assert (
        source_post(
            api,
            document,
            "release",
            {"scan_id": scanned.json()["scan_id"], "reason": "Cannot override failed scanner"},
        ).status_code
        == 409
    )
    doc = api["session"].get(Document, UUID(document))
    with api["app"].state.raw_storage.open(doc.storage_key) as source:
        assert source.read() == CSV
    assert api["session"].scalar(select(func.count()).select_from(PilotSourceRelease)) == 0


def test_actual_hash_mismatch_does_not_reach_scanner_or_release(api):
    document = upload(api, release=False).json()["id"]
    doc = api["session"].get(Document, UUID(document))
    (api["root"] / doc.storage_key).write_bytes(b"changed")

    class MustNotScan:
        def scan(self, *args, **kwargs):
            pytest.fail("Mismatched source bytes reached the scanner")

    api["app"].state.scanner = MustNotScan()
    scanned = source_post(api, document, "scan")
    assert scanned.status_code == 200, scanned.text
    assert scanned.json()["verdict"] == "MISMATCH"
    row = api["session"].get(PilotSourceScan, UUID(scanned.json()["scan_id"]))
    assert row.actual_sha256 == hashlib.sha256(b"changed").hexdigest()
    assert row.sha256 == hashlib.sha256(CSV).hexdigest()
    set_role(api, "owner")
    assert (
        source_post(
            api,
            document,
            "release",
            {"scan_id": str(row.id), "reason": "Mismatched source blocked"},
        ).status_code
        == 409
    )


def test_scan_and_release_requests_are_pinned_even_when_release_is_semantically_identical(api):
    document = upload(api, release=False).json()["id"]
    first_key, second_key = uuid4(), uuid4()
    scanned = source_post(api, document, "scan", key=first_key)
    again = source_post(api, document, "scan", key=first_key)
    assert again.json()["scan_id"] == scanned.json()["scan_id"]
    assert (
        source_post(api, document, "scan", {"reason": "Changed request"}, key=first_key).status_code
        == 409
    )
    set_role(api, "owner")
    payload = {"scan_id": scanned.json()["scan_id"], "reason": "Explicit clean release"}
    first = source_post(api, document, "release", payload, key=second_key)
    second = source_post(api, document, "release", payload)
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json()["release_id"] == second.json()["release_id"]
    assert source_post(api, document, "scan", key=second_key).status_code == 409
    assert api["session"].scalar(select(func.count()).select_from(PilotSourceScan)) == 1
    assert api["session"].scalar(select(func.count()).select_from(PilotSourceRelease)) == 1
    assert api["session"].scalar(select(func.count()).select_from(PilotSourceRequest)) == 3


def test_new_failed_scan_closes_old_release_without_rewriting_history(api):
    document = upload(api).json()["id"]
    initial = status(api, document)

    class UnavailableScanner:
        def scan(self, *args, **kwargs):
            return ScanVerdict("UNAVAILABLE")

    api["app"].state.scanner = UnavailableScanner()
    next_scan = source_post(api, document, "scan")
    assert next_scan.status_code == 200, next_scan.text
    assert status(api, document)["state"] == "UNAVAILABLE"
    assert initial["scan_id"] != status(api, document)["scan_id"]
    assert api["session"].scalar(select(func.count()).select_from(PilotSourceRelease)) == 1
    assert api["session"].scalar(select(func.count()).select_from(PilotSourceScan)) == 2
    assert source_post(api, document, "process").status_code == 409
    set_role(api, "owner")
    assert (
        source_post(
            api,
            document,
            "release",
            {"scan_id": initial["scan_id"], "reason": "Cannot release stale scan"},
        ).status_code
        == 409
    )


def test_cross_tenant_or_viewer_cannot_read_or_change_scan_state(api):
    document = upload(api, release=False).json()["id"]
    set_role(api, "owner", subject="b")
    for action in ("scan", "release"):
        data = {"reason": "Wrong tenant"} | (
            {"scan_id": str(uuid4())} if action == "release" else {}
        )
        assert source_post(api, document, action, data, subject="b", org="b").status_code == 404
    assert source_post(api, document, "scan", subject="viewer").status_code == 403
    assert (
        api["client"]
        .get(path(api, "b") + f"/{document}/source-status", headers=headers(api, "b"))
        .status_code
        == 404
    )
    assert api["session"].scalar(select(func.count()).select_from(PilotSourceScan)) == 0


def test_scan_release_audit_is_immutable_and_original_metadata_cannot_be_rebound(api):
    document = upload(api).json()["id"]
    scan = api["session"].scalar(select(PilotSourceScan))
    release = api["session"].scalar(select(PilotSourceRelease))
    assert scan.actor_id == api["users"]["a"].id
    assert scan.db_principal and scan.effective_role and scan.created_at and scan.reason
    assert release.actor_id != scan.actor_id and release.db_principal and release.created_at
    for table in ("pilot_source_scans", "pilot_source_releases", "pilot_source_requests"):
        for statement in (f"UPDATE {table} SET reason='changed'", f"DELETE FROM {table}"):
            with pytest.raises(DBAPIError, match="immutable"):
                with api["session"].begin_nested():
                    api["session"].execute(text(statement))
    with pytest.raises(DBAPIError, match="immutable"):
        with api["session"].begin_nested():
            api["session"].execute(
                text("UPDATE documents SET sha256=:hash WHERE id=:id"),
                {"hash": "c" * 64, "id": UUID(document)},
            )


def test_release_rechecks_actual_bytes_after_clean_scan(api):
    document = upload(api, release=False).json()["id"]
    scanned = source_post(api, document, "scan").json()["scan_id"]
    doc = api["session"].get(Document, UUID(document))
    (api["root"] / doc.storage_key).write_bytes(b"changed after scan")
    set_role(api, "owner")
    response = source_post(
        api, document, "release", {"scan_id": scanned, "reason": "Actual bytes must still match"}
    )
    assert response.status_code == 409, response.text
    assert api["session"].scalar(select(func.count()).select_from(PilotSourceRelease)) == 0
