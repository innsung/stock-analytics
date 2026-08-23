import subprocess
import sys
from types import SimpleNamespace

import pytest

from src import main as app_main
from src.cli import command_dispatcher


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_importing_main_does_not_load_heavy_runtime_modules():
    script = (
        "import sys; import src.main; "
        "blocked={'pandas','requests','config.settings','database.database',"
        "'src.kis.client','src.shadow.engine','src.collector.collectors'}; "
        "print(','.join(sorted(blocked.intersection(sys.modules))))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == ""


@pytest.mark.parametrize("failure", (None, RuntimeError("command failed")))
def test_run_command_always_closes_database_connection(monkeypatch, failure):
    connection = FakeConnection()

    def dispatch(*args, **kwargs):
        if failure:
            raise failure

    monkeypatch.setattr(command_dispatcher, "dispatch_command", dispatch)

    if failure:
        with pytest.raises(RuntimeError, match="command failed"):
            app_main.run_command(
                SimpleNamespace(command="backtest"),
                settings_loader=lambda: SimpleNamespace(db_path="test.db"),
                connector=lambda _path: connection,
            )
    else:
        app_main.run_command(
            SimpleNamespace(command="backtest"),
            settings_loader=lambda: SimpleNamespace(db_path="test.db"),
            connector=lambda _path: connection,
        )

    assert connection.closed


def test_run_command_skips_database_for_connectionless_command(monkeypatch):
    received = {}

    def dispatch(conn, *args, **kwargs):
        received["conn"] = conn

    monkeypatch.setattr(command_dispatcher, "dispatch_command", dispatch)

    app_main.run_command(
        SimpleNamespace(command="build-final-release-bundle-v321"),
        settings_loader=lambda: pytest.fail("settings-free command loaded settings"),
        connector=lambda _path: pytest.fail("connectionless command opened the database"),
    )

    assert received["conn"] is None


def test_run_command_loads_settings_without_database_when_required(monkeypatch):
    settings = SimpleNamespace(db_path="test.db")
    received = {}

    def dispatch(conn, dispatched_settings, *args, **kwargs):
        received.update(conn=conn, settings=dispatched_settings)

    monkeypatch.setattr(command_dispatcher, "dispatch_command", dispatch)

    app_main.run_command(
        SimpleNamespace(command="audit-kakao-zero-ratio-merger-v321"),
        settings_loader=lambda: settings,
        connector=lambda _path: pytest.fail("settings-only command opened the database"),
    )

    assert received == {"conn": None, "settings": settings}
