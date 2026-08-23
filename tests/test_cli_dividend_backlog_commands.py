from types import SimpleNamespace

import pytest

from src.cli.dividend_backlog_commands import run_dividend_backlog_command


def test_unknown_dividend_backlog_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported dividend-backlog command"):
        run_dividend_backlog_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_router_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="route-historical-backlog-v321",
        actionable_queue_csv=str(tmp_path / "missing.csv"),
        output_csv=str(tmp_path / "output.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.82\]"):
        run_dividend_backlog_command(SimpleNamespace(), args)
