"""D2 unit/contract tests: recording doubles and real ORM plans, no database."""

import ast
import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import emit_evidence
import psycopg
import pytest
from acceptance import product_v11 as fixture
from acceptance.p0_diagnostics import (
    D2_SUBSTAGES,
    seed_outcome,
    validate_diagnostic,
)
from acceptance.p0_fixture_errors import failure_detail, postgres_sqlstate
from app.admin import operator_context
from app.db.models import Organization, OrganizationMembership, User
from gate import Blocked, verify_source
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.unitofwork import SaveUpdateAll, UOWTransaction
from sqlalchemy.util.topological import sort

CANARY = "synthetic-private-sql-cookie-bearer-value-do-not-publish"
PHASE = "synthetic_identities"
ROOT = Path(__file__).resolve().parents[3]


def extension(error, substage="users_flush"):
    return failure_detail(error, "FIXTURE_PERSISTENCE_ERROR", PHASE, substage)


def body(d2, *, status="BLOCKED", reason="FIXTURE_PERSISTENCE_ERROR", phase=PHASE):
    value = {
        "status": status,
        "e2e": "NOT_EXECUTED",
        "diagnostic": {"reason_code": reason, "phase": phase},
        "diagnostic_d2": d2,
    }
    if status == "BLOCKED":
        value["missing"] = ["fixture_or_witness_verification_failed"]
    else:
        value["check"] = "persisted_financial_invariants"
    return json.dumps(value).encode()


@pytest.mark.parametrize(
    "error,category,state",
    [
        (psycopg.errors.UniqueViolation(CANARY), "postgresql", "23505"),
        (psycopg.errors.RaiseException(CANARY), "postgresql", "P0001"),
        (psycopg.errors.InternalError_(CANARY), "postgresql", "XX000"),
        (psycopg.Error(CANARY), "postgresql", None),
        (
            IntegrityError(
                CANARY, {"private": CANARY}, psycopg.errors.UniqueViolation(CANARY)
            ),
            "sqlalchemy_integrity",
            "23505",
        ),
        (
            DBAPIError(
                CANARY,
                {"private": CANARY},
                psycopg.errors.InsufficientPrivilege(CANARY),
            ),
            "sqlalchemy_database",
            "42501",
        ),
        (DBAPIError(CANARY, {}, RuntimeError(CANARY)), "sqlalchemy_database", None),
        (SQLAlchemyError(CANARY), "sqlalchemy_orm", None),
        (ValueError(CANARY), "unexpected", None),
        (OSError(CANARY), "filesystem", None),
        (TimeoutError(CANARY), "timeout", None),
        (RuntimeError(CANARY), "unexpected", None),
    ],
)
def test_actual_exception_types_are_categorized_without_messages(
    error, category, state
):
    d2 = extension(error)
    assert (d2["exception_category"], d2["sqlstate"]) == (category, state)
    outcome, public = seed_outcome(2, body(d2))
    assert outcome == "BLOCKED" and public["diagnostic_d2"] == d2
    assert CANARY not in json.dumps(public)
    validate_diagnostic(public)


@pytest.mark.parametrize(
    "state", ["private", "23505\n", "23505" + CANARY, "00000", 23505, None]
)
def test_unreliable_or_success_sqlstate_is_absent(state):
    class SyntheticDriverError(psycopg.Error):
        sqlstate = state

    assert postgres_sqlstate(SyntheticDriverError(CANARY)) is None


def test_arbitrary_error_attributes_cannot_claim_postgresql():
    error = RuntimeError(CANARY)
    error.sqlstate = "23505"
    error.orig = psycopg.errors.UniqueViolation(CANARY)
    assert postgres_sqlstate(error) is None
    assert extension(error)["sqlstate"] is None


def test_driver_chain_is_bounded_cycle_safe_and_never_stringified():
    class Unprintable(RuntimeError):
        def __str__(self):
            raise AssertionError("Private exception must never be formatted")

    root = SQLAlchemyError(CANARY)
    root.__cause__ = psycopg.errors.ForeignKeyViolation(CANARY)
    assert postgres_sqlstate(root) == "23503"
    cycle = Unprintable()
    cycle.__cause__ = cycle
    assert postgres_sqlstate(cycle) is None
    assert CANARY not in json.dumps(extension(cycle))
    chain = RuntimeError()
    cursor = chain
    for _ in range(20):
        cursor.__cause__ = RuntimeError()
        cursor = cursor.__cause__
    cursor.__cause__ = psycopg.errors.UniqueViolation(CANARY)
    assert postgres_sqlstate(chain) is None


@pytest.mark.parametrize(
    "change",
    [
        {"substage": CANARY},
        {"substage": []},
        {"sqlstate": "42"},
        {"sqlstate": "00000"},
        {"sqlstate": CANARY},
        {"exception_category": CANARY},
        {"stage": CANARY},
        {"fixture_status": "PASS"},
        {"e2e_executed": True},
        {"reason_code": "FIXTURE_PREPARED"},
        {"schema_version": True},
        {"extra": CANARY},
        {"substage": "documents_flush"},
        {"exception_category": "unexpected", "sqlstate": "23505"},
    ],
)
def test_d2_malformed_or_contradictory_extensions_fail_closed(change):
    d2 = extension(psycopg.errors.UniqueViolation(CANARY))
    d2.update(change)
    status, public = seed_outcome(2, body(d2))
    assert status == "FAIL" and public["reason_code"] == "DIAGNOSTIC_UNAVAILABLE"
    assert CANARY not in json.dumps(public)


@pytest.mark.parametrize(
    "phase,substage", [(p, s) for p, ss in D2_SUBSTAGES.items() for s in ss]
)
def test_all_closed_substages_have_safe_diagnostics(phase, substage):
    reason = {
        "postgres_preflight": "DATABASE_PREFLIGHT_ERROR",
        "alembic": "ALEMBIC_PREFLIGHT_ERROR",
        "oidc_discovery": "OIDC_DISCOVERY_ERROR",
        "fixture_or_witness": "UNEXPECTED_INTERNAL_EXCEPTION",
    }.get(phase, "FIXTURE_PERSISTENCE_ERROR")
    d2 = failure_detail(RuntimeError(CANARY), reason, phase, substage)
    assert d2["sqlstate"] is None and d2["e2e_executed"] is False
    assert CANARY not in json.dumps(d2)


def test_d2_requires_matching_nonzero_exit_status_and_cannot_be_fixture_success():
    d2 = extension(RuntimeError(CANARY))
    assert seed_outcome(0, body(d2))[0] == "FAIL"
    raw = json.dumps(
        {
            "status": "FIXTURE_ONLY",
            "e2e": "NOT_EXECUTED",
            "roster": "private",
            "financial_records_inserted": 0,
            "diagnostic_d2": d2,
        }
    ).encode()
    assert seed_outcome(0, raw)[0] == "FAIL"


@pytest.fixture
def recording_seed(monkeypatch, tmp_path):
    """Models transaction order and audit contract only; not PostgreSQL triggers."""
    for key, value in {
        "PRODUCT_OWNER_SUBJECT": "demo-owner",
        "PRODUCT_ANALYST_SUBJECT": "demo-analyst",
        "OIDC_ISSUER_URL": "http://127.0.0.1:9100",
    }.items():
        monkeypatch.setenv(key, value)
    state = SimpleNamespace(
        events=[],
        settings={},
        persisted={},
        pending=[],
        journal=[],
        failure=None,
        actor_missing=False,
        actor_disabled=False,
        committed=False,
        rolled_back=False,
        disposed=False,
        audit_missing=False,
    )

    def fail(substage):
        if state.failure == substage:
            raise DBAPIError(
                CANARY, {"private": CANARY}, psycopg.errors.RaiseException(CANARY)
            )

    class RecordingSession:
        def __init__(self, _db):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @contextmanager
        def begin(self):
            state.events.append("transaction_begin")
            try:
                yield self
                fail("transaction_commit")
                state.committed = True
            except Exception:
                state.rolled_back = True
                state.persisted.clear()
                state.journal.clear()
                raise
            finally:
                state.settings.clear()

        def scalar(self, sql):
            if "pilot_user_access" in str(sql):
                return False if state.actor_disabled else None
            return 0

        def get(self, cls, identity):
            state.events.append("operator_lookup")
            fail("operator_context")
            return None if state.actor_missing else state.persisted.get((cls, identity))

        def execute(self, sql, params):
            assert "set_config(:setting,:value,true)" in str(sql)
            assert not state.pending
            state.settings[params["setting"]] = params["value"]
            state.events.append(params["setting"])

        def add_all(self, objects):
            state.pending.extend(objects)

        def add(self, obj):
            state.pending.append(obj)

        def flush(self):
            names = {type(o).__name__ for o in state.pending}
            stage = {
                "User": "users_flush",
                "Organization": "organizations_flush",
                "UserIdentity": "oidc_identities_flush",
                "OrganizationMembership": "memberships_flush",
                "Document": "documents_flush",
            }[next(iter(names))]
            assert len(names) == 1
            state.events.append(stage)
            fail(stage)
            for obj in state.pending:
                if isinstance(obj, (Organization, OrganizationMembership)):
                    assert state.settings.get("fla.operator_actor")
                    actor = UUID(state.settings["fla.operator_actor"])
                    assert (User, actor) in state.persisted
                    state.journal.append(
                        SimpleNamespace(
                            action=obj.__tablename__ + ".insert",
                            request_id=state.settings["fla.operator_request"],
                            actor_id=actor,
                            reason=state.settings["fla.operator_reason"],
                        )
                    )
                if obj.id is None:
                    obj.id = uuid4()
                state.persisted[type(obj), obj.id] = obj
            state.pending.clear()

        def scalars(self, _sql):
            state.events.append("audit_verify")
            fail("audit_verify")
            return SimpleNamespace(
                all=lambda: [] if state.audit_missing else state.journal
            )

    monkeypatch.setattr(fixture, "Session", RecordingSession)
    monkeypatch.setattr(fixture, "preflight", lambda: {"status": "PREFLIGHT_ONLY"})
    monkeypatch.setattr(fixture, "DIRECTORY", tmp_path)
    monkeypatch.setattr(
        fixture,
        "engine",
        lambda: SimpleNamespace(dispose=lambda: setattr(state, "disposed", True)),
    )
    return state


def test_seed_uses_real_operator_context_after_users_before_organizations(
    recording_seed,
):
    state = recording_seed
    result = fixture.seed()
    assert (
        result["status"] == "FIXTURE_ONLY" and result["financial_records_inserted"] == 0
    )
    assert state.committed and not state.rolled_back and state.disposed
    assert state.events == [
        "transaction_begin",
        "users_flush",
        "operator_lookup",
        "fla.operator_actor",
        "fla.operator_reason",
        "fla.operator_request",
        "organizations_flush",
        "oidc_identities_flush",
        "memberships_flush",
        "documents_flush",
        "audit_verify",
    ]
    assert len(state.journal) == 4 and len({r.request_id for r in state.journal}) == 1
    assert state.settings == {}
    assert result["e2e"] == "NOT_EXECUTED"


@pytest.mark.parametrize("mode", ["actor_missing", "actor_disabled"])
def test_rejected_operator_stops_before_organization_and_rolls_back(
    recording_seed, mode
):
    setattr(recording_seed, mode, True)
    result = fixture.seed()
    assert result["status"] == "BLOCKED"
    assert result["diagnostic_d2"]["substage"] == "operator_context"
    assert result["diagnostic_d2"]["exception_category"] == "operator_rejected"
    assert "organizations_flush" not in recording_seed.events
    assert (
        recording_seed.rolled_back
        and not recording_seed.persisted
        and recording_seed.disposed
    )


@pytest.mark.parametrize(
    "substage",
    [
        "users_flush",
        "operator_context",
        "organizations_flush",
        "oidc_identities_flush",
        "memberships_flush",
        "documents_flush",
        "audit_verify",
        "transaction_commit",
    ],
)
def test_each_write_failure_is_located_and_rolled_back_without_leak(
    recording_seed, substage
):
    recording_seed.failure = substage
    result = fixture.seed()
    assert (
        result["status"] == "BLOCKED"
        and result["diagnostic_d2"]["substage"] == substage
    )
    assert (
        result["diagnostic_d2"]["sqlstate"] == "P0001"
    )  # synthetic driver exception only
    assert (
        recording_seed.rolled_back
        and not recording_seed.persisted
        and recording_seed.disposed
    )
    assert CANARY not in json.dumps(result)
    assert seed_outcome(2, json.dumps(result).encode())[0] == "BLOCKED"


def test_absent_audit_fails_and_transaction_is_not_committed(recording_seed):
    recording_seed.audit_missing = True
    result = fixture.seed()
    assert (
        result["status"] == "FAIL"
        and result["diagnostic_d2"]["substage"] == "audit_verify"
    )
    assert result["diagnostic_d2"]["exception_category"] == "assertion"
    assert recording_seed.rolled_back and not recording_seed.committed
    assert seed_outcome(1, json.dumps(result).encode())[0] == "FAIL"


def test_roster_failure_after_commit_is_uncertain_fixture_not_e2e(
    recording_seed, monkeypatch
):
    original = Path.write_text

    def fail_roster(path, *args, **kwargs):
        if path.name == "roster.json":
            raise OSError(CANARY)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_roster)
    result = fixture.seed()
    assert result["status"] == "BLOCKED"
    assert result["diagnostic_d2"]["substage"] == "roster_write"
    assert result["diagnostic_d2"]["exception_category"] == "filesystem"
    assert recording_seed.committed and not recording_seed.rolled_back
    assert recording_seed.disposed and result["e2e"] == "NOT_EXECUTED"
    assert CANARY not in json.dumps(result)


def test_existing_operator_helper_rejects_absent_actor_and_missing_reason():
    state = SimpleNamespace(get=lambda *_: None)
    for reason in ["", " ", CANARY]:
        with pytest.raises(ValueError):
            operator_context(state, uuid4(), reason)


def test_real_sqlalchemy_uow_plan_for_old_mixed_flush_schedules_organizations_first():
    # Real ORM dependency plan only, without connecting or executing any SQL.
    with Session() as session:
        session.add_all(
            [Organization(name="DEMO"), User(display_name="DEMO", email=None)]
        )
        work = UOWTransaction(session)
        for state in session._new:
            work.register_object(state)
        actions = work._generate_actions()
        ordered = [
            a.mapper.local_table.name
            for a in sort(work.dependencies, sorted(actions, key=lambda a: a.sort_key))
            if isinstance(a, SaveUpdateAll)
        ]
        assert ordered == ["organizations", "users"]


def migration(name):
    spec = importlib.util.spec_from_file_location(
        "d2_migration", ROOT / "backend/migrations/versions" / name
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_guard_requires_attribution_before_organization_return_and_keeps_audit():
    m = migration("0007_pilot_access.py")
    guard = m.GUARDS.split("CREATE FUNCTION pilot_access_guard()")[1].split(
        "CREATE FUNCTION pilot_access_audit()"
    )[0]
    assert guard.index("current_setting('fla.operator_actor'") < guard.index(
        "TG_TABLE_NAME = 'organizations'"
    )
    assert "NOT EXISTS(SELECT 1 FROM users WHERE id=actor)" in guard
    assert "users" not in m.ACCESS_TABLES and "organizations" in m.ACCESS_TABLES
    assert "organization_memberships" in m.ACCESS_TABLES
    assert "INSERT INTO pilot_access_journal" in m.GUARDS
    assert "AFTER INSERT OR UPDATE OR DELETE" in Path(m.__file__).read_text()
    for name in [
        "0008_pilot_intake.py",
        "0009_source_quarantine.py",
        "0010_personal_saved_views.py",
    ]:
        source = Path(migration(name).__file__).read_text()
        assert "CREATE OR REPLACE FUNCTION pilot_access_guard" not in source
        assert "DISABLE TRIGGER" not in source


def test_runtime_still_seeds_with_nonprivileged_migrator_and_no_identity_switch():
    source = (ROOT / "bench/p0/runtime.py").read_text()
    assert "CREATE ROLE p0_migrator LOGIN PASSWORD" in source
    assert "NOSUPERUSER NOCREATEDB NOCREATEROLE" in source
    tree = ast.parse(source)
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and any(
            isinstance(a, ast.Constant)
            and a.value == "synthetic_document_identity_fixture"
            for a in n.args
        )
    ]
    assert len(calls) == 1
    assert any(
        k.arg == "extra_env"
        and isinstance(k.value, ast.Dict)
        and any(
            isinstance(v, ast.Name) and v.id == "migration_url" for v in k.value.values
        )
        for k in calls[0].keywords
    )
    assert "SET ROLE" not in source and "DISABLE TRIGGER" not in source


def test_emitter_keeps_d2_closed_and_hash_receipt_without_private_values(
    tmp_path, capsys
):
    d2 = extension(psycopg.errors.UniqueViolation(CANARY))
    status, public = seed_outcome(2, body(d2))
    (tmp_path / "result.json").write_text(
        json.dumps(
            {"status": status, "e2e_executed": False, "fixture_diagnostic": public}
        )
    )
    emit_evidence.emit(tmp_path)
    assert CANARY not in capsys.readouterr().out
    public["diagnostic_d2"]["traceback"] = CANARY
    (tmp_path / "result.json").write_text(json.dumps({"fixture_diagnostic": public}))
    with pytest.raises(SystemExit, match="diagnostic schema guard"):
        emit_evidence.emit(tmp_path)
    assert capsys.readouterr().out == ""


def test_source_lock_rejects_unreviewed_fixture_bytes(tmp_path):
    # Includes the real frozen original manifest plus the exact D2 fixture overlay.
    verify_source(ROOT)
    from gate import DIAGNOSTIC_SOURCE_OVERLAY

    baseline, _ = DIAGNOSTIC_SOURCE_OVERLAY["backend/acceptance/product_v11.py"]
    (tmp_path / "bench/p0").mkdir(parents=True)
    (tmp_path / "backend/acceptance").mkdir(parents=True)
    (tmp_path / "bench/p0/v23-source.sha256").write_text(
        baseline + "  backend/acceptance/product_v11.py\n"
    )
    (tmp_path / "backend/acceptance/product_v11.py").write_text(CANARY)
    with pytest.raises(Blocked):
        verify_source(tmp_path)
