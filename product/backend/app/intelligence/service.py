"""Serialized claims, bounded execution, immutable terminal candidate snapshots."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import monotonic
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Document, ExtractedField, ExtractionRun
from app.domain.types import ProcessingStatus
from app.intelligence.execution import execute
from app.intelligence.schema import (
    ERROR_MESSAGES,
    EXTRACTOR_VERSION,
    PARSER_VERSION,
    SCHEMA_VERSION,
    ProcessingError,
)

logger = logging.getLogger("financial_leakage")
ACTIVE = {"queued", "processing"}


def scoped_runs(access, document_id):
    return select(ExtractionRun).where(
        ExtractionRun.organization_id == access.organization_id,
        ExtractionRun.document_id == document_id,
    )


def lock_document(session, access, document_id):
    document = session.scalar(
        select(Document)
        .where(Document.organization_id == access.organization_id, Document.id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


def claim(session, access, document_id, request_key: UUID, settings, reprocess=False):
    from app.financial.service import lock_authority

    lock_authority(session, access)
    document = lock_document(session, access, document_id)
    now = datetime.now(UTC)
    latest = session.scalar(
        scoped_runs(access, document_id).order_by(ExtractionRun.version_number.desc()).limit(1)
    )
    if latest and latest.status in ACTIVE and latest.lease_until and latest.lease_until < now:
        latest.status = "failed"
        latest.error_code = "interrupted"
        latest.finished_at = now
        latest.lease_until = None
        document.processing_status = ProcessingStatus.FAILED
        session.flush()
    existing = session.scalar(
        scoped_runs(access, document_id).where(ExtractionRun.request_key == str(request_key))
    )
    if existing or (latest and not reprocess):
        session.commit()
        return document, existing or latest, False
    if latest and latest.status in ACTIVE:
        raise HTTPException(409, "This document is already being processed")
    number = latest.version_number + 1 if latest else 1
    if number > settings.max_extraction_attempts:
        raise HTTPException(409, "The configured processing attempt limit has been reached")
    run = ExtractionRun(
        organization_id=access.organization_id,
        document_id=document.id,
        initiated_by=access.user_id,
        previous_run_id=latest.id if latest else None,
        version_number=number,
        request_key=str(request_key),
        status="queued",
        parser_version=PARSER_VERSION,
        extractor_version=EXTRACTOR_VERSION,
        schema_version=SCHEMA_VERSION,
        provider="deterministic-explicit-labels",
        document_sha256=document.sha256,
        structured={},
        warnings=[],
        processing_limits=settings.processing_limits.model_dump(),
        lease_until=now + timedelta(seconds=settings.processing_limits.timeout_seconds + 15),
    )
    session.add(run)
    document.processing_status = ProcessingStatus.QUEUED
    session.commit()
    return document, run, True


def process(session, storage, access, document_id, request_key, settings, reprocess=False):
    document, run, created = claim(session, access, document_id, request_key, settings, reprocess)
    if not created:
        return run
    from app.financial.service import lock_authority

    lock_authority(session, access)
    run.status = "processing"
    run.started_at = datetime.now(UTC)
    document.processing_status = ProcessingStatus.PROCESSING
    session.commit()
    started = monotonic()
    result = None
    code = None
    try:
        result = execute(storage, document, settings.processing_limits, settings.max_upload_bytes)
    except ProcessingError as exc:
        code = exc.code if exc.code in ERROR_MESSAGES else "schema_validation"
    except Exception:
        # Never store exception text, which may include paths or sensitive input.
        code = "provider_unavailable"
    from app.financial.service import lock_authority

    lock_authority(session, access)
    document = lock_document(session, access, document_id)
    session.refresh(run)
    if run.status not in ACTIVE:
        session.commit()
        return run  # A recovered expired lease cannot be overwritten by a late worker.
    if result is not None:
        run.status = result.status
        run.structured = result.structured
        run.warnings = result.warnings
        run.provider = result.provider
        run.parser_version = result.parser_version
        run.extractor_version = result.extractor_version
        run.schema_version = result.schema_version
        for fact in result.fields:
            value = fact.normalized_value
            session.add(
                ExtractedField(
                    organization_id=access.organization_id,
                    document_id=document.id,
                    extraction_run_id=run.id,
                    path=fact.path,
                    raw_value=fact.raw_value,
                    normalized_value=str(value).lower() if isinstance(value, bool) else value,
                    numeric_value=Decimal(value)
                    if fact.value_type == "decimal" and value is not None
                    else None,
                    value_type=fact.value_type,
                    confidence=fact.confidence,
                    reason=fact.reason,
                    source=fact.source,
                )
            )
    else:
        run.status = "failed"
        run.error_code = code
    run.finished_at = datetime.now(UTC)
    run.lease_until = None
    document.processing_status = ProcessingStatus(run.status)
    session.commit()
    logger.info(
        "extraction_completed",
        extra={
            "organization_id": str(access.organization_id),
            "document_id": str(document_id),
            "extraction_run_id": str(run.id),
            "document_type": document.document_type.value,
            "processing_status": run.status,
            "duration_ms": round((monotonic() - started) * 1000),
            "parser_version": run.parser_version,
            "extractor_version": run.extractor_version,
        },
    )
    return run


def serialize_run(session, run, *, include_fields=True):
    fields = []
    if include_fields:
        rows = session.scalars(
            select(ExtractedField)
            .where(
                ExtractedField.organization_id == run.organization_id,
                ExtractedField.document_id == run.document_id,
                ExtractedField.extraction_run_id == run.id,
            )
            .order_by(ExtractedField.path, ExtractedField.id)
        ).all()
        fields = [
            {
                "id": str(row.id),
                "path": row.path,
                "raw_value": row.raw_value,
                "normalized_value": (row.normalized_value == "true")
                if row.value_type == "boolean" and row.normalized_value is not None
                else row.normalized_value,
                "value_type": row.value_type,
                "confidence": row.confidence,
                "reason": row.reason,
                "source": row.source,
            }
            for row in rows
        ]
    return {
        "id": str(run.id),
        "organization_id": str(run.organization_id),
        "document_id": str(run.document_id),
        "version_number": run.version_number,
        "previous_run_id": str(run.previous_run_id) if run.previous_run_id else None,
        "status": run.status,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "parser_version": run.parser_version,
        "extractor_version": run.extractor_version,
        "schema_version": run.schema_version,
        "provider": run.provider,
        "document_sha256": run.document_sha256,
        "error_code": run.error_code,
        "error_message": ERROR_MESSAGES.get(run.error_code) if run.error_code else None,
        "warnings": run.warnings,
        "structured": run.structured if include_fields else {},
        "fields": fields,
    }
