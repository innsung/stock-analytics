from types import SimpleNamespace

import pytest

from src.cli.market_followup_audit_commands import run_market_followup_audit_command


def test_unknown_market_followup_audit_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported market-followup audit command"):
        run_market_followup_audit_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_trading_halt_missing_input_preserves_phase_context(tmp_path):
    settings = SimpleNamespace(dart_api_key="test")
    args = SimpleNamespace(
        command="audit-historical-administrative-trading-halts-v321",
        actionable_queue_csv=str(tmp_path / "missing.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"),
        documents_dir=str(tmp_path / "documents"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 6\.12\]"):
        run_market_followup_audit_command(settings, args)
