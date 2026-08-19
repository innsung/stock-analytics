from types import SimpleNamespace

import pytest

from src.cli.kind_commands import run_kind_command


def test_unknown_kind_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported KIND command"):
        run_kind_command(SimpleNamespace(command="unknown"))


def test_crosscheck_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="crosscheck-kind-dividends-v321",
        market_exdate_queue_csv=str(tmp_path / "missing.csv"),
        output_csv=str(tmp_path / "output.csv"),
        audit_csv=str(tmp_path / "audit.csv"),
        timeout_seconds=1.0,
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.16\]"):
        run_kind_command(args)
