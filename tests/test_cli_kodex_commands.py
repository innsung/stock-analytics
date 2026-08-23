from types import SimpleNamespace

import pytest

from src.cli.kodex_commands import run_kodex_command


def test_unknown_kodex_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported KODEX command"):
        run_kodex_command(SimpleNamespace(command="unknown"))


def test_selfcheck_reports_registered_commands(capsys):
    run_kodex_command(SimpleNamespace(command="phase516-selfcheck"))
    output = capsys.readouterr().out
    assert "crosscheck-kind-dividends-v321: REGISTERED" in output
    assert "PHASE516_APPLIED" in output
