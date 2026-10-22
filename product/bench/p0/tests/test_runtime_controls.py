"""Scoped teardown/authorization contracts; Docker calls are explicit doubles."""

import json
from types import SimpleNamespace

import runtime
from sqlalchemy.engine import make_url


def test_unauthorized_executor_never_removes_preexisting_private_context(
    monkeypatch, tmp_path
):
    private = tmp_path / "preexisting"
    private.mkdir()
    (private / "keep.txt").write_text("preexisting context")
    evidence = tmp_path / "evidence"
    monkeypatch.setattr(runtime, "PRIVATE", private)
    monkeypatch.setattr(runtime, "EVIDENCE", evidence)
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    assert runtime.execute() == 2
    assert (private / "keep.txt").read_text() == "preexisting context"
    result = json.loads((evidence / "result.json").read_text())
    assert result["status"] == "BLOCKED" and not result["e2e_executed"]
    assert result["cleanup"] == "NOT_STARTED"


def setup_cleanup(monkeypatch, tmp_path, label):
    private = tmp_path / "private"
    private.mkdir()
    (private / "instance.json").write_text(json.dumps({"id": "this-test-instance"}))
    (private / "environment.json").write_text("ephemeral test-only secret")
    monkeypatch.setattr(runtime, "PRIVATE", private)
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    commands = []

    def command(arguments, **_kwargs):
        commands.append(arguments)
        return SimpleNamespace(returncode=0, stdout=label + "\n")

    monkeypatch.setattr(runtime.subprocess, "run", command)
    return private, commands


def test_cleanup_preserves_docker_container_with_foreign_instance_label(
    monkeypatch, tmp_path
):
    private, commands = setup_cleanup(monkeypatch, tmp_path, "foreign-instance")
    runtime.cleanup()
    assert not private.exists()
    assert all("rm" not in command for command in commands)


def test_cleanup_removes_only_its_matching_container_and_private_files(
    monkeypatch, tmp_path
):
    private, commands = setup_cleanup(monkeypatch, tmp_path, "this-test-instance")
    (tmp_path / "keep-history.txt").write_text("historical")
    runtime.cleanup()
    assert (
        not private.exists()
        and (tmp_path / "keep-history.txt").read_text() == "historical"
    )
    assert commands[-1] == ["docker", "rm", "-f", "finleak-p0-postgres"]


def test_child_environment_does_not_inherit_cloud_or_production_tokens(monkeypatch):
    for name in (
        "GITHUB_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "AZURE_CLIENT_SECRET",
        "OIDC_CLIENT_SECRET",
    ):
        monkeypatch.setenv(name, "synthetic-forbidden-sentinel")
    env = runtime.base_env()
    assert "synthetic-forbidden-sentinel" not in env.values()


def test_generated_database_url_preserves_credentials_without_changing_target():
    url = make_url(runtime.database_url("finleak_p0", "synthetic:?#@"))
    assert url.password == "synthetic:?#@"
    assert url.drivername == "postgresql+psycopg" and url.username == "finleak_p0"
    assert url.host == "127.0.0.1" and url.port == 5432
    assert url.database == "finleak_product_v11_test"
