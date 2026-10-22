import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Contract,
    Document,
    ExtractedField,
    ExtractionRun,
    Invoice,
    OrganizationMembership,
)
from app.intelligence.service import claim
from tests.intelligence_fixtures import fixture_bytes, pdf_bytes
from tests.test_documents import api as api
from tests.test_documents import headers, path, upload
from tests.test_intelligence import CASES

pytestmark = pytest.mark.integration


@pytest.fixture
def intelligence_api(api):
    api["app"].state.settings.max_upload_bytes = 1024 * 1024
    return api


def document(api, name="one-line-invoice"):
    case = next(case for case in CASES if case["name"] == name)
    data, mime = fixture_bytes(case)
    response = upload(
        api,
        content=data,
        filename="synthetic." + case["format"],
        mime=mime,
        kind=case["document_type"],
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def processing(api, document_id, *, action="process", key=None, subject="a", org="a"):
    return api["client"].post(
        path(api, org) + f"/{document_id}/{action}",
        headers={**headers(api, subject), "Idempotency-Key": str(key or uuid4())},
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_authenticated_upload_process_review_and_download(intelligence_api, case):
    api = intelligence_api
    document_id = document(api, case["name"])
    response = processing(api, document_id)
    assert response.status_code == 200, response.text
    run = response.json()["run"]
    assert run["status"] == case["status"]
    assert run["organization_id"] == str(api["orgs"]["a"])
    assert run["document_id"] == document_id
    assert run["parser_version"] and run["schema_version"] and run["extractor_version"]
    assert run["document_sha256"] == api["session"].get(Document, UUID(document_id)).sha256
    for field in run["fields"]:
        assert field["raw_value"] and field["source"]["format"] == case["format"]
    detail = api["client"].get(path(api) + f"/{document_id}/extraction", headers=headers(api))
    assert detail.json()["run"] == run
    assert detail.headers["cache-control"] == "no-store"
    original = api["client"].get(path(api) + f"/{document_id}/content", headers=headers(api))
    assert hashlib.sha256(original.content).hexdigest() == run["document_sha256"]
    amounts = (
        api["session"]
        .scalars(
            select(ExtractedField).where(
                ExtractedField.value_type == "decimal", ExtractedField.numeric_value.is_not(None)
            )
        )
        .all()
    )
    assert all(isinstance(field.numeric_value, Decimal) for field in amounts)


@pytest.mark.parametrize(
    "action",
    [
        "process",
        "reprocess",
        "extraction",
        "extraction-runs",
        "extraction-runs/00000000-0000-0000-0000-000000000001",
    ],
)
def test_unauthenticated_extraction_endpoints_are_denied(intelligence_api, action):
    api = intelligence_api
    endpoint = path(api) + f"/{uuid4()}/{action}"
    response = (
        api["client"].post(endpoint, headers={"Idempotency-Key": str(uuid4())})
        if action in {"process", "reprocess"}
        else api["client"].get(endpoint)
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "action", ["process", "reprocess", "extraction", "extraction-runs", "evidence"]
)
def test_cross_tenant_documents_runs_and_evidence_are_denied(intelligence_api, action):
    api = intelligence_api
    document_id = document(api)
    run = processing(api, document_id).json()["run"]
    suffix = f"extraction-runs/{run['id']}" if action == "evidence" else action
    endpoint = path(api, "b") + f"/{document_id}/{suffix}"
    response = (
        api["client"].post(endpoint, headers={**headers(api, "b"), "Idempotency-Key": str(uuid4())})
        if action in {"process", "reprocess"}
        else api["client"].get(endpoint, headers=headers(api, "b"))
    )
    assert response.status_code == 404
    assert "Synthetic Logistics" not in response.text


def test_run_id_cannot_be_attached_to_another_document(intelligence_api):
    api = intelligence_api
    first = document(api)
    second = document(api, "csv-invoice")
    run = processing(api, first).json()["run"]
    response = api["client"].get(
        path(api) + f"/{second}/extraction-runs/{run['id']}", headers=headers(api)
    )
    assert response.status_code == 404


@pytest.mark.parametrize("action", ["process", "reprocess"])
def test_viewer_can_inspect_but_cannot_process(intelligence_api, action):
    api = intelligence_api
    document_id = document(api)
    assert processing(api, document_id, action=action, subject="viewer").status_code == 403
    processing(api, document_id)
    read = api["client"].get(
        path(api) + f"/{document_id}/extraction", headers=headers(api, "viewer")
    )
    assert read.status_code == 200 and read.json()["run"]["fields"]


def test_revocation_applies_to_processing_and_evidence(intelligence_api):
    api = intelligence_api
    document_id = document(api)
    processing(api, document_id)
    membership = api["session"].scalar(
        select(OrganizationMembership).where(OrganizationMembership.user_id == api["users"]["a"].id)
    )
    api["session"].delete(membership)
    api["session"].flush()
    assert processing(api, document_id).status_code == 404
    assert (
        api["client"]
        .get(path(api) + f"/{document_id}/extraction", headers=headers(api))
        .status_code
        == 404
    )


def test_idempotency_and_version_history_never_create_authoritative_entities(intelligence_api):
    api = intelligence_api
    document_id = document(api)
    key = uuid4()
    first = processing(api, document_id, key=key).json()["run"]
    assert processing(api, document_id, key=key).json()["run"] == first
    assert processing(api, document_id).json()["run"] == first
    retry_key = uuid4()
    second = processing(api, document_id, action="reprocess", key=retry_key).json()["run"]
    assert second["version_number"] == 2 and second["previous_run_id"] == first["id"]
    assert processing(api, document_id, action="reprocess", key=retry_key).json()["run"] == second
    old = (
        api["client"]
        .get(path(api) + f"/{document_id}/extraction-runs/{first['id']}", headers=headers(api))
        .json()["run"]
    )
    assert old == first
    page = (
        api["client"]
        .get(path(api) + f"/{document_id}/extraction-runs?limit=1&offset=1", headers=headers(api))
        .json()
    )
    assert page["total"] == 2 and len(page["items"]) == 1
    assert page["items"][0]["id"] == first["id"] and page["items"][0]["fields"] == []
    assert api["session"].scalar(select(func.count()).select_from(Invoice)) == 0
    assert api["session"].scalar(select(func.count()).select_from(Contract)) == 0


@pytest.mark.parametrize("key", [None, "not-a-uuid"])
def test_request_key_is_required_and_validated(intelligence_api, key):
    api = intelligence_api
    request_headers = headers(api)
    if key:
        request_headers["Idempotency-Key"] = key
    response = api["client"].post(path(api) + f"/{uuid4()}/process", headers=request_headers)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("data", "code"),
    [(b"%PDF-1.4 broken\n%%EOF", "corrupt_document"), (pdf_bytes(encrypted=True), "encrypted_pdf")],
)
def test_unsupported_original_is_rejected_before_any_extraction_authority(
    intelligence_api, data, code
):
    api = intelligence_api
    # Unsupported originals now fail safely inside the protected upload child,
    # before registration/scan/download or any ExtractionRun can be created.
    response = upload(api, filename="synthetic.pdf", content=data, mime="application/pdf")
    assert response.status_code == 415, response.text
    assert "Traceback" not in response.text and code not in response.text
    assert api["session"].scalar(select(func.count()).select_from(ExtractionRun)) == 0
    assert api["session"].scalar(select(func.count()).select_from(Document)) == 0
    assert not list(api["root"].rglob("source"))


def test_active_attempts_are_serialized_and_stale_lease_is_audited(intelligence_api):
    from app.auth.dependencies import OrganizationAccess
    from app.domain.types import MembershipRole

    api = intelligence_api
    document_id = UUID(document(api))
    access = OrganizationAccess(api["orgs"]["a"], api["users"]["a"].id, MembershipRole.ANALYST)
    _, first, created = claim(
        api["session"], access, document_id, uuid4(), api["app"].state.settings
    )
    assert created and first.status == "queued"
    assert processing(api, document_id, action="reprocess").status_code == 409
    first.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    api["session"].commit()
    second = processing(api, document_id, action="reprocess").json()["run"]
    api["session"].refresh(first)
    assert first.status == "failed" and first.error_code == "interrupted"
    assert second["status"] == "processed" and second["previous_run_id"] == str(first.id)


def test_retry_limit_is_configurable_and_idempotency_still_works(intelligence_api):
    api = intelligence_api
    api["app"].state.settings.max_extraction_attempts = 1
    document_id = document(api)
    first = processing(api, document_id).json()["run"]
    assert processing(api, document_id, action="reprocess").status_code == 409
    assert processing(api, document_id).json()["run"] == first


def test_database_rejects_cross_tenant_field_provenance(intelligence_api):
    api = intelligence_api
    document_id = document(api)
    run = processing(api, document_id).json()["run"]
    field = api["session"].scalar(select(ExtractedField))
    with pytest.raises(IntegrityError), api["session"].begin_nested():
        api["session"].add(
            ExtractedField(
                organization_id=api["orgs"]["b"],
                document_id=UUID(document_id),
                extraction_run_id=UUID(run["id"]),
                path=field.path,
                raw_value=field.raw_value,
                normalized_value=field.normalized_value,
                numeric_value=field.numeric_value,
                value_type=field.value_type,
                confidence=field.confidence,
                reason=field.reason,
                source=field.source,
            )
        )
        api["session"].flush()


def test_database_rejects_multiple_active_attempts(intelligence_api):
    from app.auth.dependencies import OrganizationAccess
    from app.domain.types import MembershipRole

    api = intelligence_api
    document_id = UUID(document(api))
    access = OrganizationAccess(api["orgs"]["a"], api["users"]["a"].id, MembershipRole.ANALYST)
    _, first, _ = claim(api["session"], access, document_id, uuid4(), api["app"].state.settings)
    with pytest.raises(IntegrityError), api["session"].begin_nested():
        api["session"].add(
            ExtractionRun(
                organization_id=access.organization_id,
                document_id=document_id,
                initiated_by=access.user_id,
                version_number=2,
                request_key=str(uuid4()),
                status="queued",
                parser_version=first.parser_version,
                extractor_version=first.extractor_version,
                schema_version=first.schema_version,
                provider=first.provider,
                document_sha256=first.document_sha256,
                structured={},
                warnings=[],
                processing_limits={},
            )
        )
        api["session"].flush()
