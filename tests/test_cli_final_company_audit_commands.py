from types import SimpleNamespace

import pytest

from src.cli.final_company_audit_commands import run_final_company_audit_command


def test_unknown_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported final company-audit command"):
        run_final_company_audit_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_third_party_capital_missing_input_preserves_phase(tmp_path):
    args = SimpleNamespace(command="audit-hd-ksoe-third-party-capital-v321",
        actionable_queue_csv=str(tmp_path/"missing.csv"), disclosures_csv=str(tmp_path/"d.csv"),
        documents_dir=str(tmp_path/"docs"), evidence_output_csv=str(tmp_path/"e.csv"),
        audit_output_csv=str(tmp_path/"a.csv"), summary_json=str(tmp_path/"s.json"))
    with pytest.raises(SystemExit, match=r"Phase 6\.24"):
        run_final_company_audit_command(SimpleNamespace(dart_api_key="test"), args)
