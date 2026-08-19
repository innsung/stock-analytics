from types import SimpleNamespace

import pytest

from src.cli.historical_dividend_commands import run_historical_dividend_command


def test_unknown_historical_dividend_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported historical-dividend command"):
        run_historical_dividend_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_parser_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="parse-historical-dividend-decisions-v321",
        acquisition_csv=str(tmp_path / "missing.csv"),
        output_csv=str(tmp_path / "output.csv"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.69\]"):
        run_historical_dividend_command(SimpleNamespace(), args)
