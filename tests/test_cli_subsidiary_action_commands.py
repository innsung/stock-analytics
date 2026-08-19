from types import SimpleNamespace

import pytest

from src.cli.subsidiary_action_commands import run_subsidiary_action_command


def test_unknown_subsidiary_action_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported subsidiary-action command"):
        run_subsidiary_action_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_priority_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="prioritize-current-resolution-backlog-v321",
        resolved_verification_csv=str(tmp_path / "missing.csv"),
        output_csv=str(tmp_path / "output.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.55\]"):
        run_subsidiary_action_command(SimpleNamespace(), args)
