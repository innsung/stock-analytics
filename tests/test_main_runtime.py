from types import SimpleNamespace

import pytest

from src import main as app_main
from src.cli import command_dispatcher


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.mark.parametrize("failure", (None, RuntimeError("command failed")))
def test_run_command_always_closes_database_connection(monkeypatch, failure):
    connection = FakeConnection()
    monkeypatch.setattr(app_main, "get_settings", lambda: SimpleNamespace(db_path="test.db"))
    monkeypatch.setattr(app_main, "connect", lambda _path: connection)

    def dispatch(*args, **kwargs):
        if failure:
            raise failure

    monkeypatch.setattr(command_dispatcher, "dispatch_command", dispatch)

    if failure:
        with pytest.raises(RuntimeError, match="command failed"):
            app_main.run_command(SimpleNamespace(command="backtest"))
    else:
        app_main.run_command(SimpleNamespace(command="backtest"))

    assert connection.closed


def test_run_command_skips_database_for_connectionless_command(monkeypatch):
    monkeypatch.setattr(
        app_main,
        "get_settings",
        lambda: pytest.fail("settings-free command loaded settings"),
    )
    monkeypatch.setattr(
        app_main,
        "connect",
        lambda _path: pytest.fail("connectionless command opened the database"),
    )
    received = {}

    def dispatch(conn, *args, **kwargs):
        received["conn"] = conn

    monkeypatch.setattr(command_dispatcher, "dispatch_command", dispatch)

    app_main.run_command(SimpleNamespace(command="build-final-release-bundle-v321"))

    assert received["conn"] is None


def test_run_command_loads_settings_without_database_when_required(monkeypatch):
    settings = SimpleNamespace(db_path="test.db")
    monkeypatch.setattr(app_main, "get_settings", lambda: settings)
    monkeypatch.setattr(
        app_main,
        "connect",
        lambda _path: pytest.fail("settings-only command opened the database"),
    )
    received = {}

    def dispatch(conn, dispatched_settings, *args, **kwargs):
        received.update(conn=conn, settings=dispatched_settings)

    monkeypatch.setattr(command_dispatcher, "dispatch_command", dispatch)

    app_main.run_command(SimpleNamespace(command="audit-kakao-zero-ratio-merger-v321"))

    assert received == {"conn": None, "settings": settings}
