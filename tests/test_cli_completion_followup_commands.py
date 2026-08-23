from types import SimpleNamespace

import pytest

from src.cli.completion_followup_commands import run_completion_followup_command


def test_unknown_completion_followup_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported completion-followup command"):
        run_completion_followup_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_asset_transfer_missing_input_preserves_phase_context(tmp_path):
    settings = SimpleNamespace(dart_api_key="test")
    args = SimpleNamespace(
        command="audit-asset-transfer-completion-reports-v321",
        actionable_queue_csv=str(tmp_path / "missing.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"),
        documents_dir=str(tmp_path / "documents"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 6\.15\]"):
        run_completion_followup_command(settings, args)
