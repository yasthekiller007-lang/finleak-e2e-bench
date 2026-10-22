"""Producer phases, with database/issuer/storage doubles explicitly isolated."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from acceptance import product_v11 as fixture
from acceptance.p0_diagnostics import seed_outcome

CANARY = "synthetic-private-message-not-for-evidence"


@pytest.fixture
def configured(monkeypatch):
    for key, value in {
        "PRODUCT_V11_ACCEPTANCE": "1",
        "PRODUCT_SYNTHETIC_ACCOUNTS_ONLY": "1",
        "FLA_ENVIRONMENT": "test",
        "PRODUCT_OWNER_SUBJECT": "synthetic-owner",
        "PRODUCT_ANALYST_SUBJECT": "synthetic-analyst",
        "FLA_DATABASE_URL": "postgresql+psycopg://synthetic:private@127.0.0.1/finleak_product_v11_test",
        "OIDC_ISSUER_URL": "http://127.0.0.1:9100",
    }.items():
        monkeypatch.setenv(key, value)


def fake_preflight(
    monkeypatch, *, version=170011, role=False, head="0010", metadata=None, failure=None
):
    class Connection:
        def __enter__(self):
            if failure == "connection":
                raise RuntimeError(CANARY)
            return self

        def __exit__(self, *_args):
            return False

        def scalar(self, sql):
            if "server_version_num" in str(sql):
                return version
            if "pg_roles" in str(sql):
                return role
            if failure == "alembic":
                raise RuntimeError(CANARY)
            return head

    disposed = []
    db = SimpleNamespace(connect=lambda: Connection(), dispose=lambda: disposed.append(True))
    monkeypatch.setattr(fixture, "engine", lambda: db)
    monkeypatch.setattr(
        fixture.ScriptDirectory,
        "from_config",
        lambda _config: SimpleNamespace(get_current_head=lambda: "0010"),
    )

    def provider(*_args):
        if failure == "oidc":
            raise RuntimeError(CANARY)
        return (
            metadata
            if metadata is not None
            else {
                "issuer": "http://127.0.0.1:9100",
                "code_challenge_methods_supported": ["S256"],
                "id_token_signing_alg_values_supported": ["RS256"],
            }
        )

    monkeypatch.setattr(fixture, "provider_json", provider)
    return disposed


@pytest.mark.parametrize(
    "options,reason,phase",
    [
        ({"version": 160000}, "POSTGRES_VERSION_MISMATCH", "postgres_preflight"),
        ({"role": True}, "POSTGRES_ROLE_REJECTED", "postgres_preflight"),
        ({"head": "0009"}, "ALEMBIC_HEAD_MISMATCH", "alembic"),
        ({"metadata": {}}, "OIDC_DISCOVERY_REJECTED", "oidc_discovery"),
        ({"failure": "connection"}, "DATABASE_PREFLIGHT_ERROR", "postgres_preflight"),
        ({"failure": "alembic"}, "ALEMBIC_PREFLIGHT_ERROR", "alembic"),
        ({"failure": "oidc"}, "OIDC_DISCOVERY_ERROR", "oidc_discovery"),
    ],
)
def test_preflight_reports_only_verified_phase_constants(
    configured, monkeypatch, options, reason, phase
):
    disposed = fake_preflight(monkeypatch, **options)
    result = fixture.preflight()
    assert result["status"] == "BLOCKED" and result["e2e"] == "NOT_EXECUTED"
    assert result["diagnostic"] == {"reason_code": reason, "phase": phase}
    status, public = seed_outcome(2, json.dumps(result).encode())
    assert status == "BLOCKED" and public["reason_code"] == reason
    assert disposed == [True] and CANARY not in json.dumps(result)


def test_preflight_success_does_not_claim_authentication(configured, monkeypatch):
    fake_preflight(monkeypatch)
    value = fixture.preflight()
    assert value["status"] == "PREFLIGHT_ONLY"
    assert value["oidc_discovery"] == "AVAILABLE_NOT_AUTHENTICATED"
    assert value["e2e"] == "NOT_EXECUTED"


def test_engine_construction_error_is_safe(configured, monkeypatch):
    def fail():
        raise RuntimeError(CANARY)

    monkeypatch.setattr(fixture, "engine", fail)
    result = fixture.preflight()
    assert result["diagnostic"]["reason_code"] == "DATABASE_PREFLIGHT_ERROR"
    assert CANARY not in json.dumps(result)


def test_guard_preserves_rejection_before_any_network(monkeypatch):
    monkeypatch.delenv("PRODUCT_V11_ACCEPTANCE", raising=False)
    monkeypatch.setattr(fixture, "engine", lambda: pytest.fail("Must not connect"))
    result = fixture.preflight()
    assert result["diagnostic"]["reason_code"] == "MISSING_TEST_PRECONDITION"


def test_invalid_configuration_preserves_rejection(configured, monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://production.invalid/" + CANARY)
    result = fixture.guard()
    assert result["diagnostic"]["reason_code"] == "INVALID_LOOPBACK_CONFIGURATION"
    assert CANARY not in json.dumps(result)


def synthetic_seed_doubles(monkeypatch, tmp_path, failure=None):
    monkeypatch.setattr(fixture, "preflight", lambda: {"status": "PREFLIGHT_ONLY"})
    monkeypatch.setattr(fixture, "DIRECTORY", tmp_path)
    disposed = []
    monkeypatch.setattr(
        fixture, "engine", lambda: SimpleNamespace(dispose=lambda: disposed.append(True))
    )

    def fail(phase):
        if failure == phase:
            raise RuntimeError(CANARY)
        if failure == "assertion" and phase == "documents":
            raise AssertionError(CANARY)

    class SessionDouble:
        def __init__(self, _db):
            self.objects = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @contextmanager
        def begin(self):
            yield self
            fail("transaction")

        def scalar(self, _sql):
            return 1 if failure == "not_empty" else 0

        def add_all(self, objects):
            self.objects += objects
            fail("identities")

        def flush(self):
            for obj in self.objects:
                obj.id = uuid4()

        def add(self, _obj):
            pass

    monkeypatch.setattr(fixture, "Session", SessionDouble)

    class StorageDouble:
        def __init__(self, _root):
            fail("storage")

        def put(self, key, _stream, **_kwargs):
            fail("documents")
            return SimpleNamespace(file_size=1, key=key, sha256="0" * 64)

    monkeypatch.setattr(fixture, "LocalObjectStorage", StorageDouble)
    if failure == "roster":
        original = type(tmp_path).write_text

        def write(path, *args, **kwargs):
            if path.name == "roster.json":
                raise OSError(CANARY)
            return original(path, *args, **kwargs)

        monkeypatch.setattr(type(tmp_path), "write_text", write)
    return disposed


@pytest.mark.parametrize(
    "failure,reason,phase,status",
    [
        ("storage", "FIXTURE_PERSISTENCE_ERROR", "storage_initialization", "BLOCKED"),
        ("not_empty", "TEST_DATABASE_NOT_EMPTY", "test_database", "BLOCKED"),
        ("identities", "FIXTURE_PERSISTENCE_ERROR", "synthetic_identities", "BLOCKED"),
        ("documents", "FIXTURE_PERSISTENCE_ERROR", "synthetic_documents", "BLOCKED"),
        ("transaction", "FIXTURE_PERSISTENCE_ERROR", "fixture_transaction", "BLOCKED"),
        ("roster", "FIXTURE_PERSISTENCE_ERROR", "fixture_roster", "BLOCKED"),
        ("assertion", "FIXTURE_INVARIANT_FAILED", "synthetic_documents", "FAIL"),
    ],
)
def test_seed_internal_phases_preserve_semantics_without_raw_exceptions(
    configured, monkeypatch, tmp_path, failure, reason, phase, status
):
    disposed = synthetic_seed_doubles(monkeypatch, tmp_path, failure)
    result = fixture.seed()
    assert result["status"] == status
    assert result["diagnostic"] == {"reason_code": reason, "phase": phase}
    assert CANARY not in json.dumps(result) and disposed == [True]
    outcome, public = seed_outcome(2 if status == "BLOCKED" else 1, json.dumps(result).encode())
    assert outcome == status and public["reason_code"] == reason


def test_existing_roster_blocks_without_replacing_it(configured, monkeypatch, tmp_path):
    synthetic_seed_doubles(monkeypatch, tmp_path)
    (tmp_path / "roster.json").write_text("preserved synthetic roster")
    value = fixture.seed()
    assert value["diagnostic"]["reason_code"] == "FIXTURE_DIRECTORY_NOT_FRESH"
    assert (tmp_path / "roster.json").read_text() == "preserved synthetic roster"


def test_successful_source_only_fixture_keeps_the_contract(configured, monkeypatch, tmp_path):
    synthetic_seed_doubles(monkeypatch, tmp_path)
    value = fixture.seed()
    assert value["status"] == "FIXTURE_ONLY" and value["financial_records_inserted"] == 0
    assert seed_outcome(0, json.dumps(value).encode())[0] == "FIXTURE_ONLY"
    assert value["e2e"] == "NOT_EXECUTED"


def test_cli_unexpected_internal_exception_is_normalized(monkeypatch, capsys):
    def fail():
        raise RuntimeError(CANARY)

    monkeypatch.setattr(fixture, "seed", fail)
    monkeypatch.setattr("sys.argv", ["acceptance.product_v11", "seed"])
    assert fixture.main() == 2
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["diagnostic"]["reason_code"] == "UNEXPECTED_INTERNAL_EXCEPTION"
    assert CANARY not in output
