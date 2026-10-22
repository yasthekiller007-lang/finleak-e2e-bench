"""Pure validation, explicit Session doubles, API boundaries and compiled PostgreSQL SQL.
No native database, OIDC login or concurrency execution is claimed.
"""

import importlib.util
import io
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app.auth.dependencies import get_database_session, get_organization_access
from app.core.config import Settings
from app.main import create_app
from app.saved_views import service as s
from app.saved_views.models import SavedExceptionView as V
from app.saved_views.schema import CreateView, Definition, DeleteView, UpdateView, normalized_name

ORG, USER, ID = UUID(int=20), UUID(int=21), UUID(int=22)
ACCESS = SimpleNamespace(organization_id=ORG, user_id=USER, role="viewer")
NOW = datetime(2026, 10, 19, tzinfo=UTC)


def body(**overrides):
    return {
        "name": "CFO USD",
        "view_type": "anomalies",
        "criteria": {"currency": "USD"},
        **overrides,
    }


def row(**overrides):
    return SimpleNamespace(
        id=ID,
        organization_id=ORG,
        user_id=USER,
        name="CFO USD",
        slot=1,
        normalized_name="cfo usd",
        view_type="anomalies",
        format_version=1,
        criteria={"currency": "USD", "sort": "newest", "needs_review": False},
        page_size=20,
        revision=1,
        created_at=NOW,
        updated_at=NOW,
        **overrides,
    )


class Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class Boundary:
    """Returns explicitly scripted values, never emulates SQL/locks/isolation."""

    def __init__(self, scalar=(), rows=(), flush_error=False):
        self.values = iter(scalar)
        self.rows = rows
        self.statements = []
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flush_error = flush_error

    def scalar(self, stmt):
        self.statements.append(stmt)
        return next(self.values)

    def scalars(self, stmt):
        self.statements.append(stmt)
        return Rows(self.rows)

    def add(self, obj):
        self.added.append(obj)
        obj.id = ID
        obj.created_at = NOW
        obj.updated_at = NOW

    def flush(self):
        if self.flush_error:
            raise IntegrityError("synthetic", {}, Exception("synthetic"))

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1


def compiled(stmt):
    return stmt.compile(dialect=postgresql.dialect())


@pytest.mark.parametrize(
    "name,expected",
    [
        ("  CFO   USD  ", "cfo usd"),
        ("ＣＦＯ USD", "cfo usd"),
        ("Straße", "strasse"),
        ("STRASSE", "strasse"),
        ("Σς", "σσ"),
    ],
)
def test_normalized_names(name, expected):
    assert normalized_name(name) == expected


@pytest.mark.parametrize(
    "name", ["", " ", "x" * 81, "bad\nname", "bad\x00name", "bad\u202ename", "bad\ud800"]
)
def test_invalid_name(name):
    with pytest.raises(ValidationError):
        CreateView.model_validate(body(name=name))


@pytest.mark.parametrize(
    "criteria",
    [
        {"amount": "1000"},
        {"token": "secret"},
        {"after": "cursor"},
        {"citations": []},
        {"decision": {"reason": "x"}},
        {"organization_id": str(ORG)},
        {"user_id": str(USER)},
        {"current": "true"},
        {"needs_review": 1},
        {"missing_contract": None},
        {"currency": 20},
        {"supplier": None},
        {"q": False},
        {"sort": "random"},
        {"outcome": "invented"},
        {"decision_status": "approved"},
        {"currency": "usd"},
        {"invoice_source_id": "not-a-uuid"},
        {"contract_source_id": str(ID), "missing_contract": True},
        {"q": "x" * 161},
        {"supplier": "x" * 121},
        {"supplier": "bad\x7fvalue"},
        {"q": "bad\u2066text"},
        {"created_from": "2026-10-19"},
        {"created_from": "2026-02-30T00:00:00Z"},
        {"created_from": "2026-10-19T00:00:00Z", "created_to": "2026-10-18T00:00:00Z"},
        {"created_to": 123},
        ["currency", "USD"],
    ],
)
def test_strict_criteria(criteria):
    with pytest.raises(ValidationError):
        CreateView.model_validate(body(criteria=criteria))


@pytest.mark.parametrize(
    "extra",
    [
        {"user_id": str(USER)},
        {"organization_id": str(ORG)},
        {"format_version": 2},
        {"format_version": True},
        {"page_size": 2},
        {"page_size": 20.0},
        {"page_size": True},
        {"view_type": "dashboard"},
    ],
)
def test_request_scope_and_format_cannot_be_injected(extra):
    with pytest.raises(ValidationError):
        CreateView.model_validate(body(**extra))


def test_route_defaults_explicit_override_and_exact_strings():
    assert Definition.model_validate({"view_type": "review", "criteria": {}}).criteria.needs_review
    assert not Definition.model_validate(
        {"view_type": "anomalies", "criteria": {}}
    ).criteria.needs_review
    value = Definition.model_validate(
        {
            "view_type": "review",
            "criteria": {
                "needs_review": False,
                "supplier": "Acme ",
                "q": "  rate ",
                "invoice_source_id": str(ID),
            },
        }
    )
    assert (
        not value.criteria.needs_review
        and value.criteria.supplier == "Acme "
        and value.criteria.q == "rate"
    )
    assert value.criteria.invoice_source_id == ID


@pytest.mark.parametrize(
    "value",
    [
        {"expected_revision": 0, "name": "X"},
        {"expected_revision": "1", "name": "X"},
        {"expected_revision": True, "name": "X"},
        {"expected_revision": 1},
        {"expected_revision": 1, "name": None},
        {"expected_revision": 1, "definition": None},
        {"expected_revision": 1, "after": "cursor"},
    ],
)
def test_update_revision_and_explicit_patch(value):
    with pytest.raises(ValidationError):
        UpdateView.model_validate(value)


def test_scoped_sql_is_parameterized_owner_and_tenant_bounded():
    stmt = s.list_statement(ACCESS, "x%_'\\", "anomalies", 10, ID)
    c = compiled(stmt)
    text = str(c)
    assert "organization_id =" in text and "user_id =" in text and "id >" in text
    assert "ORDER BY saved_exception_views.id ASC" in text and stmt._limit_clause.value == 11
    assert "x%" not in text and ORG in c.params.values() and USER in c.params.values()
    assert "count(" not in text.lower()
    assert "%x\\%\\_'\\\\%" in c.params.values()


def test_creation_uses_membership_lock_and_only_personal_table():
    db = Boundary([uuid4(), None], rows=[1, 2, 4])
    result = s.create(db, ACCESS, CreateView.model_validate(body()))
    assert result.slot == 3 and result.organization_id == ORG and result.user_id == USER
    assert "FOR UPDATE" in str(compiled(db.statements[0]))
    assert "organization_memberships.user_id =" in str(compiled(db.statements[0]))
    assert len(db.added) == 1 and isinstance(db.added[0], V) and db.commits == 0
    assert set(result.criteria) <= {
        "q",
        "currency",
        "current",
        "needs_review",
        "missing_contract",
        "sort",
    }


def test_quota_and_membership_loss():
    db = Boundary([uuid4(), None], rows=list(range(1, 51)))
    with pytest.raises(HTTPException) as exc:
        s.create(db, ACCESS, CreateView.model_validate(body()))
    assert (
        exc.value.status_code == 409
        and exc.value.detail["code"] == "SAVED_VIEW_LIMIT"
        and not db.added
    )
    db = Boundary([None, None])
    with pytest.raises(HTTPException) as exc:
        s.create(db, ACCESS, CreateView.model_validate(body()))
    assert exc.value.status_code == 404 and not db.added


def test_unique_failure_rolls_back_without_overwrite():
    db = Boundary([uuid4(), None], rows=[], flush_error=True)
    with pytest.raises(HTTPException) as exc:
        s.create(db, ACCESS, CreateView.model_validate(body()))
    assert exc.value.status_code == 409 and db.rollbacks == 1


@pytest.mark.parametrize(
    "bad",
    [
        SimpleNamespace(**{**vars(row()), "user_id": UUID(int=999)}),
        SimpleNamespace(**{**vars(row()), "organization_id": UUID(int=999)}),
        None,
    ],
)
def test_detail_hides_wrong_owner_or_org(bad):
    db = Boundary([bad])
    with pytest.raises(HTTPException) as exc:
        s.detail(db, ACCESS, ID)
    assert exc.value.status_code == 404
    c = compiled(db.statements[0])
    assert ORG in c.params.values() and USER in c.params.values() and ID in c.params.values()


def test_keyset_listing_and_serialization_have_no_results():
    a = row()
    b = SimpleNamespace(**{**vars(row()), "id": UUID(int=23)})
    page = s.listing(Boundary(rows=[a, b]), ACCESS, "", None, 1, None)
    assert page["has_more"] and page["next_after"] == str(ID) and len(page["items"]) == 1
    assert set(page["items"][0]) == {
        "id",
        "organization_id",
        "user_id",
        "name",
        "view_type",
        "format_version",
        "criteria",
        "page_size",
        "revision",
        "created_at",
        "updated_at",
    }
    assert s.listing(Boundary(rows=[]), ACCESS, "missing", None, 10, None)["items"] == []


def test_rename_preserves_criteria_and_uses_cas():
    current = row()
    updated = SimpleNamespace(**{**vars(current), "name": "New", "revision": 2})
    db = Boundary([uuid4(), None, current, updated])
    result = s.change(db, ACCESS, ID, UpdateView(expected_revision=1, name="New"))
    stmt = db.statements[-1]
    c = compiled(stmt)
    assert result.revision == 2 and result.criteria == current.criteria
    assert "revision =" in str(c) and "RETURNING" in str(c) and "criteria" not in stmt._values
    assert ORG in c.params.values() and USER in c.params.values() and ID in c.params.values()


def test_update_criteria_is_explicit_and_type_cannot_change():
    d = Definition.model_validate({"view_type": "anomalies", "criteria": {"currency": "EUR"}})
    db = Boundary([uuid4(), None, row(), row()])
    s.change(db, ACCESS, ID, UpdateView(expected_revision=1, definition=d))
    assert "EUR" in str(compiled(db.statements[-1]).params)
    db = Boundary([uuid4(), None, row()])
    with pytest.raises(HTTPException) as exc:
        s.change(
            db,
            ACCESS,
            ID,
            UpdateView(
                expected_revision=1,
                definition=Definition.model_validate({"view_type": "review", "criteria": {}}),
            ),
        )
    assert exc.value.status_code == 422


def test_stale_update_and_atomic_conflict_never_retry():
    for values in (
        [uuid4(), None, SimpleNamespace(**{**vars(row()), "revision": 2})],
        [uuid4(), None, row(), None],
    ):
        db = Boundary(values)
        with pytest.raises(HTTPException) as exc:
            s.change(db, ACCESS, ID, UpdateView(expected_revision=1, name="Draft"))
        assert exc.value.status_code == 409 and db.commits == 0


def test_delete_is_owner_scoped_revision_checked_and_has_no_business_cascade():
    db = Boundary([uuid4(), None, row(), ID])
    assert s.remove(db, ACCESS, ID, DeleteView(expected_revision=1))["deleted"]
    sql = str(compiled(db.statements[-1]))
    assert (
        "DELETE FROM saved_exception_views" in sql
        and "revision =" in sql
        and "user_id =" in sql
        and "organization_id =" in sql
    )
    db = Boundary([uuid4(), None, row(), None])
    with pytest.raises(HTTPException) as exc:
        s.remove(db, ACCESS, ID, DeleteView(expected_revision=1))
    assert exc.value.status_code == 409


def test_unknown_stored_version_or_injected_results_are_not_silently_dropped():
    for bad in [
        {**vars(row()), "format_version": 2},
        {**vars(row()), "criteria": {"amount": "1000"}},
    ]:
        with pytest.raises(ValidationError):
            s.serialize(SimpleNamespace(**bad))


def test_model_and_candidate_ddl_have_quota_name_and_ownership_constraints():
    sql = str(CreateTable(V.__table__).compile(dialect=postgresql.dialect()))
    for fragment in [
        "slot BETWEEN 1 AND 50",
        "UNIQUE (organization_id, user_id, slot)",
        "UNIQUE (organization_id, user_id, view_type, normalized_name)",
        "JSONB",
        "REFERENCES users",
        "REFERENCES organizations",
        "revision BETWEEN",
        "page_size IN",
    ]:
        assert fragment in sql
    assert "CASCADE" not in sql and "organization_memberships" not in sql
    spec = importlib.util.spec_from_file_location(
        "candidate", Path(__file__).parents[1] / "migrations/versions/0010_personal_saved_views.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    output = io.StringIO()
    ctx = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output, "target_metadata": V.metadata},
    )
    with Operations.context(ctx):
        m.upgrade()
    ddl = output.getvalue()
    assert m.down_revision == "0009" and "CREATE TABLE saved_exception_views" in ddl
    assert "ALTER TABLE" not in ddl and "DROP TABLE" not in ddl and "CASCADE" not in ddl
    for constraint in V.__table__.constraints:
        if constraint.name:
            assert postgresql.dialect().identifier_preparer.format_constraint(constraint) in ddl


@pytest.fixture
def client():
    app = create_app(Settings(environment="test"))
    yield TestClient(app)


def test_real_unauthenticated_endpoint_is_rejected(client):
    response = client.get(f"/api/v1/organizations/{ORG}/financial/saved-views")
    assert response.status_code == 401 and response.headers["cache-control"] == "no-store"


def test_api_contract_with_explicit_authorization_and_repository_doubles(client, monkeypatch):
    client.app.dependency_overrides[get_organization_access] = lambda: ACCESS
    db = Boundary()
    client.app.dependency_overrides[get_database_session] = lambda: db
    seen = []
    monkeypatch.setattr(s, "create", lambda session, access, b: seen.append((access, b)) or row())
    base = f"/api/v1/organizations/{ORG}/financial/saved-views"
    response = client.post(base, json=body())
    assert response.status_code == 201 and seen[0][0].user_id == USER and db.commits == 1
    for extra in [{"user_id": str(USER)}, {"criteria": {"amount": "1000"}}, {"format_version": 7}]:
        assert client.post(base, json=body(**extra)).status_code == 422
    for query in ["?limit=21", "?limit=0", "?after=wrong", "?view_type=other", "?search=%00"]:
        assert client.get(base + query).status_code == 422


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_every_mutation_has_bounded_strict_json_before_business_work(client, method):
    url = f"/api/v1/organizations/{ORG}/financial/saved-views" + (
        "" if method == "post" else f"/{ID}"
    )
    # httpx delete convenience has no content argument; request is used explicitly.
    assert (
        client.request(
            method.upper(), url, content=b"x" * 16385, headers={"content-type": "application/json"}
        ).status_code
        == 413
    )
    assert (
        client.request(
            method.upper(),
            url,
            content=b'{"name":"A","name":"B"}',
            headers={"content-type": "application/json"},
        ).status_code
        == 422
    )
    assert (
        client.request(
            method.upper(), url, content=b"{}", headers={"content-type": "text/plain"}
        ).status_code
        == 415
    )


def test_current_membership_is_rechecked_by_existing_auth_dependency():
    db = Boundary([None, None])
    with pytest.raises(HTTPException) as exc:
        get_organization_access(ORG, SimpleNamespace(id=USER), db)
    assert exc.value.status_code == 404
    sql = str(compiled(db.statements[-1]))
    assert "organization_memberships.organization_id =" in sql
    assert "organization_memberships.user_id =" in sql


def test_api_read_update_delete_bind_owner_and_commit_only_acknowledged_mutations(
    client, monkeypatch
):
    client.app.dependency_overrides[get_organization_access] = lambda: ACCESS
    db = Boundary()
    client.app.dependency_overrides[get_database_session] = lambda: db
    seen = []

    def detail(session, access, view_id):
        seen.append(("read", access.user_id, view_id))
        return row()

    def change(session, access, view_id, body):
        seen.append(("update", access.user_id, body.expected_revision, body.name))
        return SimpleNamespace(**{**vars(row()), "name": body.name, "revision": 2})

    def remove(session, access, view_id, body):
        seen.append(("delete", access.user_id, body.expected_revision))
        return {"id": str(view_id), "deleted": True}

    monkeypatch.setattr(s, "detail", detail)
    monkeypatch.setattr(s, "change", change)
    monkeypatch.setattr(s, "remove", remove)
    url = f"/api/v1/organizations/{ORG}/financial/saved-views/{ID}"
    assert client.get(url).json()["user_id"] == str(USER)
    response = client.patch(url, json={"expected_revision": 1, "name": "Renamed"})
    assert response.status_code == 200 and response.json()["revision"] == 2
    assert client.request("DELETE", url, json={"expected_revision": 2}).json()["deleted"]
    assert seen == [("read", USER, ID), ("update", USER, 1, "Renamed"), ("delete", USER, 2)]
    assert db.commits == 2
    assert (
        client.patch(
            url,
            json={
                "expected_revision": 1,
                "name": "X",
                "definition": {"view_type": "anomalies", "criteria": {}},
            },
        ).status_code
        == 422
    )
    for query in ("?token=x", "?limit=2&limit=3"):
        assert client.get(url.rsplit("/", 1)[0] + query).status_code == 422
