from types import SimpleNamespace

import pytest

from src.cli.dividend_resolution_commands import run_dividend_resolution_command


def test_unknown_dividend_resolution_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported dividend-resolution command"):
        run_dividend_resolution_command(SimpleNamespace(command="unknown"))


def test_no_dividend_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="resolve-explicit-no-dividend-v321",
        residual_csv=str(tmp_path / "missing.csv"),
        dividend_facts_csv=str(tmp_path / "facts.csv"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        business_year=2025,
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.79\]"):
        run_dividend_resolution_command(args)
