from types import SimpleNamespace

import pytest

from src.cli.spinoff_commands import run_spinoff_command


def test_unknown_spinoff_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported spin-off command"):
        run_spinoff_command(SimpleNamespace(command="unknown"))


def test_distribution_ledger_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="build-spinoff-distribution-ledger-v321",
        valuation_audit_csv=str(tmp_path / "missing.csv"),
        output_csv=str(tmp_path / "output.csv"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.50\]"):
        run_spinoff_command(args)
