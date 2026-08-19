from types import SimpleNamespace

import pytest

from src.cli.corporate_action_document_commands import run_corporate_action_document_command


def test_unknown_corporate_action_document_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported corporate-action document command"):
        run_corporate_action_document_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_candidate_manifest_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="build-corporate-action-candidate-manifest-v321",
        classified_queue_csv=str(tmp_path / "missing.csv"),
        official_candidates_csv=str(tmp_path / "official.csv"),
        output_csv=str(tmp_path / "output.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.44\]"):
        run_corporate_action_document_command(SimpleNamespace(), args)
