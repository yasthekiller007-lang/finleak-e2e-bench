"""Explicit private scan and controlled release; no extraction or financial side effects."""

import hashlib
import io
import json

from sqlalchemy import select

from app.db.models import Document
from app.financial.service import lock_authority
from app.modules.scanner import ScanVerdict
from app.operations.source_gate import SourceGateError, latest_scan
from app.operations.source_models import PilotSourceRelease, PilotSourceRequest, PilotSourceScan
from app.proof.budget import Budget, ProofError


def locked_source(session, access, document_id, *, final=False):
    lock_authority(session, access, final=final)
    document = session.scalar(
        select(Document)
        .where(
            Document.organization_id == access.organization_id,
            Document.id == document_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if document is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Document not found")
    return document


def captured_source(storage, document, budget):
    checksum, total, output = hashlib.sha256(), 0, bytearray()
    with storage.open(document.storage_key) as source:
        while chunk := source.read(65536):
            budget.read(len(chunk))
            total += len(chunk)
            checksum.update(chunk)
            output.extend(chunk)
    budget.check()
    return checksum.hexdigest(), total, bytes(output)


def request_fingerprint(operation, document_id, reason, scan_id=None):
    value = json.dumps(
        {
            "operation": operation,
            "document_id": str(document_id),
            "reason": reason,
            "scan_id": str(scan_id) if scan_id else None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(b"FLA-PILOT-SOURCE-REQUEST/1\0" + value.encode()).hexdigest()


def previous_request(session, access, document_id, key, operation, fingerprint):
    row = session.scalar(
        select(PilotSourceRequest).where(
            PilotSourceRequest.organization_id == access.organization_id,
            PilotSourceRequest.request_key == key,
        )
    )
    if row is None:
        return None
    if (
        row.document_id != document_id
        or row.operation != operation
        or row.fingerprint != fingerprint
    ):
        raise SourceGateError("source_action_idempotency_conflict")
    return session.get(
        PilotSourceScan if operation == "SCAN" else PilotSourceRelease, row.result_id
    )


def bind_request(session, access, document_id, key, operation, fingerprint, reason, result):
    session.add(
        PilotSourceRequest(
            organization_id=access.organization_id,
            document_id=document_id,
            actor_id=access.user_id,
            request_key=key,
            operation=operation,
            fingerprint=fingerprint,
            reason=reason,
            result_id=result.id,
        )
    )
    session.flush()
    return result


def scan(session, raw, scanner, access, document_id, key, reason, limits):
    document = locked_source(session, access, document_id)
    fingerprint = request_fingerprint("SCAN", document_id, reason)
    existing = previous_request(session, access, document_id, key, "SCAN", fingerprint)
    if existing:
        return existing
    budget = Budget(limits)
    actual_sha, actual_size = None, None
    try:
        actual_sha, actual_size, original = captured_source(raw, document, budget)
        if actual_sha != document.sha256 or actual_size != document.file_size:
            verdict = ScanVerdict("MISMATCH")
        else:
            verdict = scanner.scan(
                io.BytesIO(original),
                max_bytes=document.file_size,
                deadline=budget.started + budget.limits.work_seconds,
            )
    except ProofError as error:
        verdict = ScanVerdict("TIMEOUT" if error.code == "proof_work_budget" else "SUSPICIOUS")
    except (OSError, ValueError):
        verdict = ScanVerdict("UNAVAILABLE")
    previous = latest_scan(session, document)
    row = PilotSourceScan(
        organization_id=access.organization_id,
        document_id=document.id,
        actor_id=access.user_id,
        request_key=key,
        sequence=previous.sequence + 1 if previous else 1,
        sha256=document.sha256,
        file_size=document.file_size,
        actual_sha256=actual_sha,
        actual_file_size=actual_size,
        verdict=verdict.status,
        scanner_profile=verdict.profile,
        scanner_version=verdict.version,
        reason=reason,
    )
    session.add(row)
    session.flush()
    return bind_request(session, access, document_id, key, "SCAN", fingerprint, reason, row)


def release(session, raw, access, document_id, scan_id, key, reason, limits):
    document = locked_source(session, access, document_id, final=True)
    fingerprint = request_fingerprint("RELEASE", document_id, reason, scan_id)
    existing = previous_request(session, access, document_id, key, "RELEASE", fingerprint)
    if existing:
        return existing
    current = latest_scan(session, document)
    if current is None or current.id != scan_id or current.verdict != "CLEAN":
        raise SourceGateError("source_clean_current_scan_required")
    if current.sha256 != document.sha256 or current.file_size != document.file_size:
        raise SourceGateError("source_integrity_mismatch")
    try:
        actual_sha, actual_size, _ = captured_source(raw, document, Budget(limits))
    except (OSError, ValueError):
        raise SourceGateError("source_integrity_unavailable", 503) from None
    if actual_sha != document.sha256 or actual_size != document.file_size:
        raise SourceGateError("source_integrity_mismatch")
    semantic = session.scalar(
        select(PilotSourceRelease).where(
            PilotSourceRelease.organization_id == access.organization_id,
            PilotSourceRelease.document_id == document_id,
            PilotSourceRelease.scan_id == scan_id,
        )
    )
    if semantic:
        return bind_request(
            session, access, document_id, key, "RELEASE", fingerprint, reason, semantic
        )
    row = PilotSourceRelease(
        organization_id=access.organization_id,
        document_id=document_id,
        scan_id=scan_id,
        actor_id=access.user_id,
        request_key=key,
        reason=reason,
        verified_sha256=actual_sha,
        verified_file_size=actual_size,
    )
    session.add(row)
    session.flush()
    return bind_request(session, access, document_id, key, "RELEASE", fingerprint, reason, row)
