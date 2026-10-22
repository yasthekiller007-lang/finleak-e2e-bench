"""Engine ownership across caller-owned binds and failed startup."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text

from app.core.config import Settings
from app.main import create_app


def owned_engines(monkeypatch):
    engines = [create_engine("sqlite://"), create_engine("sqlite://")]
    disposed = []
    for index, engine in enumerate(engines):
        event.listen(engine, "engine_disposed", lambda _, i=index: disposed.append(i))
    pending = iter(engines)
    monkeypatch.setattr("app.main.create_database_engine", lambda _: next(pending))
    return disposed


@pytest.mark.parametrize("replacement", ["connection", "engine"])
def test_lifespan_disposes_created_engines_without_closing_caller_owned_bind(
    monkeypatch, tmp_path, replacement
):
    disposed = owned_engines(monkeypatch)
    external = create_engine("sqlite://")
    external_disposed = []
    event.listen(external, "engine_disposed", lambda _: external_disposed.append(True))
    settings = Settings(_env_file=None, environment="test", storage_root=tmp_path)
    try:
        with external.connect() as connection:
            with TestClient(create_app(settings)) as client:
                client.app.state.scanner_engine = (
                    connection if replacement == "connection" else external
                )
                client.app.state.database_engine = (
                    connection if replacement == "connection" else external
                )
            assert not connection.closed
            assert connection.scalar(text("SELECT 1")) == 1
            assert disposed == [1, 0]
            assert external_disposed == []
    finally:
        external.dispose()


def test_lifespan_cleans_both_created_engines_after_scanner_startup_failure(monkeypatch, tmp_path):
    disposed = owned_engines(monkeypatch)

    def failure(_):
        raise ValueError("synthetic startup failure")

    monkeypatch.setattr("app.main.build_scanner", failure)
    settings = Settings(_env_file=None, environment="test", storage_root=tmp_path)
    with (
        pytest.raises(ValueError, match="synthetic startup failure"),
        TestClient(create_app(settings)),
    ):
        pass
    assert disposed == [1, 0]
