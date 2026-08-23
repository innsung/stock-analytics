from types import SimpleNamespace

import pytest

from src.cli.company_applicability_commands import run_company_applicability_command


def test_unknown_company_applicability_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported company-applicability command"):
        run_company_applicability_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_lgchem_missing_input_preserves_phase_context(tmp_path):
    settings = SimpleNamespace(dart_api_key="test")
    args = SimpleNamespace(
        command="audit-lgchem-subsidiary-rights-v321",
        actionable_queue_csv=str(tmp_path / "missing.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"),
        documents_dir=str(tmp_path / "documents"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.97\]"):
        run_company_applicability_command(settings, args)
