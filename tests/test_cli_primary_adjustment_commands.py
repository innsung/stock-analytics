from types import SimpleNamespace

import pytest

from src.cli.primary_adjustment_commands import run_primary_adjustment_command


def test_unknown_primary_adjustment_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported primary-adjustment command"):
        run_primary_adjustment_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_rights_audit_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="audit-historical-rights-applicability-v321",
        terms_csv=str(tmp_path / "missing.csv"),
        execution_manifest_csv=str(tmp_path / "manifest.csv"),
        documents_dir=str(tmp_path / "documents"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.89\]"):
        run_primary_adjustment_command(SimpleNamespace(), args)
