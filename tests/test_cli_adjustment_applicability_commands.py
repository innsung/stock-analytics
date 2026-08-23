from types import SimpleNamespace

import pytest

from src.cli.adjustment_applicability_commands import run_adjustment_applicability_command


def test_unknown_adjustment_applicability_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported adjustment-applicability command"):
        run_adjustment_applicability_command(SimpleNamespace(command="unknown"))


def test_capital_reduction_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="audit-historical-capital-reductions-v321",
        terms_csv=str(tmp_path / "missing.csv"),
        execution_manifest_csv=str(tmp_path / "manifest.csv"),
        documents_dir=str(tmp_path / "documents"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.92\]"):
        run_adjustment_applicability_command(args)
