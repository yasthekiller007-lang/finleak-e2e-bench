import hashlib
import io
import os
import zipfile
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth.dependencies import get_database_session, resolve_user
from app.auth.oidc import VerifiedIdentity
from app.core.config import Settings
from app.db.models import Document, Organization, OrganizationMembership, User, UserIdentity
from app.main import create_app
from app.modules.scanner import ScanVerdict
from app.modules.storage import document_storage_key
from app.operations.intake import IntakeCoordinator
from app.operations.intake_schema import IntakeLimits
from app.operations.source_gate import ReleasedObjectStorage
from tests.identity_fixtures import ISSUER, IdentityFixture
from tests.intelligence_fixtures import pdf_bytes

pytestmark = pytest.mark.integration

PDF = pdf_bytes()
CSV = b"reference,amount\nINV-1,12.30\n"


def xlsx():
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets/></workbook>',
        )
    return result.getvalue()


@pytest.fixture
def api(db_session, tmp_path):
    identity = IdentityFixture()
    users = {
        name: resolve_user(db_session, VerifiedIdentity(ISSUER, name, "shared@example.test", name))
        for name in ("a", "b", "viewer")
    }
    organizations = {name: Organization(name=f"Organization {name}") for name in ("a", "b")}
    db_session.add_all(organizations.values())
    db_session.flush()
    for name in ("a", "b", "viewer"):
        organization = organizations["a" if name == "viewer" else name]
        db_session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=users[name].id,
                role="viewer" if name == "viewer" else "analyst",
            )
        )
    db_session.flush()
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=os.environ["TEST_DATABASE_URL"],
        storage_root=tmp_path,
        max_upload_bytes=1024,
        intake_limits=IntakeLimits(actor_operations_per_minute=1000),
    )
    app = create_app(settings, token_verifier=identity.verifier)

    def session_override():
        try:
            yield db_session
        finally:
            # Runtime closes the per-request Session and clears this on pool checkin.
            # This fixture retains one outer transaction across requests instead.
            db_session.info.pop("recovery_budget", None)
            db_session.connection().info.pop("recovery_budget", None)

    app.dependency_overrides[get_database_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as client:
        # Real services share this fixture's transaction; fresh production connections
        # cannot see its uncommitted roster. No runtime setting/header enables a bypass.
        app.state.intake = IntakeCoordinator(db_session.get_bind())
        app.state.scanner_engine = db_session.get_bind()
        app.state.storage = ReleasedObjectStorage(
            app.state.preserved_storage, db_session.get_bind()
        )

        class SyntheticScanner:
            def scan(self, source, *, max_bytes, deadline):
                return ScanVerdict("CLEAN", version="clamav/1.4.6;database/28000")

        # Protected test fixture only; no application configuration/API provides this adapter.
        app.state.scanner = SyntheticScanner()
        yield {
            "client": client,
            "identity": identity,
            "orgs": {name: org.id for name, org in organizations.items()},
            "users": users,
            "session": db_session,
            "root": tmp_path,
            "app": app,
        }


def headers(api, subject="a"):
    return {"Authorization": "Bearer " + api["identity"].token(subject)}


def path(api, org="a"):
    return f"/api/v1/organizations/{api['orgs'][org]}/documents"


def upload(
    api,
    org="a",
    subject="a",
    filename="invoice.csv",
    content=CSV,
    mime="text/csv",
    kind="invoice",
    release=True,
):
    response = api["client"].post(
        path(api, org),
        headers=headers(api, subject),
        files={"file": (filename, content, mime)},
        data={"document_type": kind},
    )
    if response.status_code == 201 and release:
        release_test_source(api, org, subject, response.json()["id"])
    return response


def release_test_source(api, org, subject, document_id):
    scanned = api["client"].post(
        path(api, org) + f"/{document_id}/scan",
        json={"reason": "Explicit synthetic fixture source scan"},
        headers={**headers(api, subject), "Idempotency-Key": str(uuid4())},
    )
    assert scanned.status_code == 200, scanned.text
    assert scanned.json()["verdict"] == "CLEAN"
    # A separate seeded owner performs the real release API. The tested caller's
    # analyst/viewer/final-approval role is never temporarily promoted.
    owner = resolve_user(api["session"], VerifiedIdentity(ISSUER, "source-release-operator"))
    member = api["session"].scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == api["orgs"][org],
            OrganizationMembership.user_id == owner.id,
        )
    )
    if member is None:
        api["session"].add(
            OrganizationMembership(organization_id=api["orgs"][org], user_id=owner.id, role="owner")
        )
        api["session"].flush()
        api["session"].commit()
    released = api["client"].post(
        path(api, org) + f"/{document_id}/release",
        json={
            "scan_id": scanned.json()["scan_id"],
            "reason": "Explicit synthetic fixture clean release",
        },
        headers={**headers(api, "source-release-operator"), "Idempotency-Key": str(uuid4())},
    )
    assert released.status_code == 200, released.text
    assert released.json()["source"]["state"] == "RELEASED"


@pytest.mark.parametrize(
    ("filename", "content", "mime"),
    [
        ("contract.pdf", PDF, "application/pdf"),
        ("invoice.csv", CSV, "text/csv"),
        ("order.xlsx", xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ],
)
def test_upload_supported_types_and_download(api, filename, content, mime):
    response = upload(api, filename=filename, content=content, mime=mime)
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["sha256"] == hashlib.sha256(content).hexdigest()
    assert document["file_size"] == len(content)
    assert document["organization_id"] == str(api["orgs"]["a"])
    assert document["uploaded_by"] == str(api["users"]["a"].id)
    assert document["processing_status"] == "pending"
    assert "storage_key" not in document
    detail = api["client"].get(path(api) + "/" + document["id"], headers=headers(api))
    assert detail.status_code == 200
    download = api["client"].get(
        path(api) + "/" + document["id"] + "/content", headers=headers(api)
    )
    assert download.status_code == 200 and download.content == content
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("kind", ["contract", "invoice", "purchase_order", "credit_note", "other"])
def test_all_document_classifications(api, kind):
    assert upload(api, kind=kind).json()["document_type"] == kind


@pytest.mark.parametrize(("subject", "organization"), [("a", "b"), ("b", "a")])
def test_cross_tenant_list_and_upload_denied(api, subject, organization):
    assert (
        api["client"].get(path(api, organization), headers=headers(api, subject)).status_code == 404
    )
    assert upload(api, organization, subject).status_code == 404
    assert not list(api["root"].rglob("source"))


@pytest.mark.parametrize(
    "endpoint",
    ["", "/00000000-0000-0000-0000-000000000001", "/00000000-0000-0000-0000-000000000001/content"],
)
def test_missing_authentication(api, endpoint):
    assert api["client"].get(path(api) + endpoint).status_code == 401
    assert (
        api["client"].post(path(api), files={"file": ("invoice.csv", CSV, "text/csv")}).status_code
        == 401
    )


def test_invalid_authentication(api):
    assert (
        api["client"].get(path(api), headers={"Authorization": "Bearer invalid"}).status_code == 401
    )


def test_cross_tenant_document_id_cannot_be_used_in_valid_organization(api):
    document_id = upload(api).json()["id"]
    for suffix in ("", "/content"):
        assert (
            api["client"]
            .get(path(api, "b") + "/" + document_id + suffix, headers=headers(api, "b"))
            .status_code
            == 404
        )
        assert (
            api["client"]
            .get(path(api) + "/" + document_id + suffix, headers=headers(api, "b"))
            .status_code
            == 404
        )


def test_viewer_can_read_but_cannot_upload(api):
    document_id = upload(api).json()["id"]
    assert api["client"].get(path(api), headers=headers(api, "viewer")).status_code == 200
    assert (
        api["client"]
        .get(path(api) + "/" + document_id + "/content", headers=headers(api, "viewer"))
        .status_code
        == 200
    )
    assert upload(api, subject="viewer").status_code == 403


def test_unknown_organization_matches_inaccessible_response(api):
    response = api["client"].get(f"/api/v1/organizations/{uuid4()}/documents", headers=headers(api))
    assert (
        response.status_code == 404
        and response.json()["error"]["message"] == "Organization not found"
    )


def test_duplicate_same_organization_is_atomic_and_other_tenant_is_independent(api):
    first = upload(api)
    second = upload(api)
    other = upload(api, "b", "b")
    assert first.status_code == 201 and second.status_code == 409 and other.status_code == 201
    assert first.json()["id"] != other.json()["id"]
    assert len(list(api["root"].rglob("source"))) == 2


@pytest.mark.parametrize(
    ("filename", "content", "mime", "status"),
    [
        ("script.exe", b"binary", "application/octet-stream", 415),
        ("invoice.csv", CSV, "application/pdf", 415),
        ("contract.pdf", b"not a pdf", "application/pdf", 415),
        ("invoice.csv", b"\x00\x01", "text/csv", 415),
        ("invoice.csv", b"\xff\xfe", "text/csv", 415),
        ("invoice.csv", b"", "text/csv", 422),
        ("invoice.csv", b"x" * 1025, "text/csv", 413),
        (
            "order.xlsx",
            b"not a zip",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            415,
        ),
    ],
)
def test_invalid_files_leave_no_objects(api, filename, content, mime, status):
    response = upload(api, filename=filename, content=content, mime=mime)
    assert response.status_code == status, response.text
    assert not list(api["root"].rglob("source"))


@pytest.mark.parametrize(
    "filename", ["../invoice.csv", "nested/invoice.csv", "invoice\r\n.csv", "%2e%2e%2finvoice.csv"]
)
def test_malicious_filenames_are_rejected(api, filename):
    assert upload(api, filename=filename).status_code == 422
    assert not list(api["root"].rglob("source"))


def test_multipart_parser_safely_removes_windows_browser_path(api):
    response = upload(api, filename=r"C:\invoice.csv")
    assert response.status_code == 201
    assert response.json()["original_filename"] == "invoice.csv"
    row = api["session"].get(Document, UUID(response.json()["id"]))
    assert row.storage_key == document_storage_key(api["orgs"]["a"], row.id)


def test_safe_generated_storage_key(api):
    document = upload(api).json()
    row = api["session"].get(Document, UUID(document["id"]))
    assert row.storage_key == document_storage_key(api["orgs"]["a"], row.id)
    assert "invoice.csv" not in row.storage_key


def test_me_only_returns_verified_memberships_and_repeated_login_does_not_duplicate_users(api):
    response = api["client"].get("/api/v1/me", headers=headers(api))
    again = api["client"].get("/api/v1/me", headers=headers(api))
    assert response.json()["id"] == again.json()["id"] == str(api["users"]["a"].id)
    assert [org["id"] for org in response.json()["organizations"]] == [str(api["orgs"]["a"])]
    assert api["session"].scalar(select(func.count()).select_from(User)) == 3


def test_first_login_maps_subject_without_email_account_linking(api):
    response = api["client"].get("/api/v1/me", headers=headers(api, "new-subject"))
    again = api["client"].get("/api/v1/me", headers=headers(api, "new-subject"))
    assert response.status_code == 200 and response.json()["organizations"] == []
    assert response.json()["id"] == again.json()["id"]
    assert response.json()["id"] != str(api["users"]["a"].id)
    assert api["session"].scalar(select(func.count()).select_from(UserIdentity)) == 4


def test_claimed_organization_and_role_do_not_grant_membership(api):
    forged = api["identity"].token(
        "a", changes={"organization_id": str(api["orgs"]["b"]), "role": "owner"}
    )
    assert (
        api["client"].get(path(api, "b"), headers={"Authorization": "Bearer " + forged}).status_code
        == 404
    )


def test_membership_revocation_takes_effect_with_same_token(api):
    token = headers(api)
    assert api["client"].get(path(api), headers=token).status_code == 200
    membership = api["session"].scalar(
        select(OrganizationMembership).where(OrganizationMembership.user_id == api["users"]["a"].id)
    )
    api["session"].delete(membership)
    api["session"].flush()
    assert api["client"].get(path(api), headers=token).status_code == 404


def test_failed_database_commit_compensates_object_write(api, monkeypatch):
    def fail():
        raise RuntimeError("test-only commit failure")

    monkeypatch.setattr(api["session"], "commit", fail)
    assert upload(api).status_code == 500
    assert not list(api["root"].rglob("source"))


@pytest.mark.parametrize("role", ["owner", "admin", "analyst"])
def test_all_write_roles_can_upload(api, role):
    membership = api["session"].scalar(
        select(OrganizationMembership).where(OrganizationMembership.user_id == api["users"]["a"].id)
    )
    membership.role = role
    api["session"].flush()
    assert upload(api).status_code == 201


def test_streamed_body_limit_does_not_trust_content_length(api):
    boundary = "phase2-boundary"
    initial = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="document_type"\r\n\r\ninvoice\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="invoice.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode()

    def body():
        yield initial
        for _ in range(20):
            yield b"x" * 65536
        yield f"\r\n--{boundary}--\r\n".encode()

    response = api["client"].post(
        path(api),
        content=body(),
        headers={**headers(api), "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 413, response.text
    assert not list(api["root"].rglob("source"))


def test_pagination_and_invalid_classification(api):
    assert upload(api, kind="extraction_result").status_code == 422
    for index in range(3):
        assert upload(api, content=f"id,amount\n{index},20\n".encode()).status_code == 201
    response = api["client"].get(path(api) + "?limit=1&offset=1", headers=headers(api))
    assert response.status_code == 200
    assert response.json()["total"] == 3 and len(response.json()["items"]) == 1
    assert api["client"].get(path(api) + "?limit=101", headers=headers(api)).status_code == 422
