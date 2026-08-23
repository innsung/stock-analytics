from types import SimpleNamespace

import pytest

from src.cli.amendment_crosscheck_commands import run_amendment_crosscheck_command


def test_unknown_amendment_crosscheck_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported amendment-crosscheck command"):
        run_amendment_crosscheck_command(SimpleNamespace(command="unknown"))


def test_duplicate_audit_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="audit-historical-amendment-duplicates-v321",
        actionable_queue_csv=str(tmp_path / "missing.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"),
        chain_csv=str(tmp_path / "chain.csv"),
        verification_csv=str(tmp_path / "verification.csv"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 6\.21\]"):
        run_amendment_crosscheck_command(args)
