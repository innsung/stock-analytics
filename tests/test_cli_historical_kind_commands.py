from types import SimpleNamespace

import pytest

from src.cli.historical_kind_commands import run_historical_kind_command


def test_unknown_historical_kind_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported historical-KIND command"):
        run_historical_kind_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_strict_evidence_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="build-historical-kind-strict-evidence-v321",
        discovery_csv=str(tmp_path / "missing.csv"),
        parsed_decisions_csv=str(tmp_path / "parsed.csv"),
        output_csv=str(tmp_path / "output.csv"),
        audit_csv=str(tmp_path / "audit.csv"),
        timeout_seconds=1.0,
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.72\]"):
        run_historical_kind_command(SimpleNamespace(), args)
