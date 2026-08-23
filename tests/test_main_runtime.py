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
