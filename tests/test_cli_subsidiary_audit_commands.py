from types import SimpleNamespace

import pytest

from src.cli.subsidiary_audit_commands import run_subsidiary_audit_command


def test_unknown_subsidiary_audit_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported subsidiary-audit command"):
        run_subsidiary_audit_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_hd_ksoe_missing_input_preserves_phase_context(tmp_path):
    settings = SimpleNamespace(dart_api_key="test")
    args = SimpleNamespace(
        command="audit-hd-ksoe-subsidiary-zero-ratio-merger-v321",
        actionable_queue_csv=str(tmp_path / "missing.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"),
        documents_dir=str(tmp_path / "documents"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 6\.04\]"):
        run_subsidiary_audit_command(settings, args)
