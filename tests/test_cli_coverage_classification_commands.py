from types import SimpleNamespace
import pytest
from src.cli.coverage_classification_commands import run_coverage_classification_command

def test_unknown_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported coverage-classification command"):
        run_coverage_classification_command(SimpleNamespace(command="unknown"))

def test_classifier_missing_input_preserves_phase(tmp_path):
    args = SimpleNamespace(command="classify-recent-corporate-actions-v321",
        priority_queue_csv=str(tmp_path/"missing.csv"), output_csv=str(tmp_path/"out.csv"),
        summary_json=str(tmp_path/"summary.json"))
    with pytest.raises(SystemExit, match=r"Phase 5\.43"):
        run_coverage_classification_command(args)
