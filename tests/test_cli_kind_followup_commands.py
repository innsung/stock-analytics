from types import SimpleNamespace

import pytest

from src.cli.kind_followup_commands import run_kind_followup_command


def test_unknown_kind_followup_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported KIND follow-up command"):
        run_kind_followup_command(SimpleNamespace(command="unknown"))


def test_batch_search_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="discover-kind-market-notices-batch-v321",
        acquisition_manifest_csv=str(tmp_path / "missing.csv"),
        output_csv=str(tmp_path / "output.csv"),
        audit_csv=str(tmp_path / "audit.csv"),
        search_start="2026-01-01",
        search_end="2026-08-19",
        timeout_seconds=1.0,
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.33\]"):
        run_kind_followup_command(args)
