from types import SimpleNamespace

import pytest

from src.cli.amendment_followup_commands import run_amendment_followup_command


def test_unknown_amendment_followup_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported amendment-followup command"):
        run_amendment_followup_command(SimpleNamespace(command="unknown"))


def test_rights_followup_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="audit-rights-offering-followups-v321",
        actionable_queue_csv=str(tmp_path / "missing.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 6\.18\]"):
        run_amendment_followup_command(args)
