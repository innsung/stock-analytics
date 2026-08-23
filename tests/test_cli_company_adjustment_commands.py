from types import SimpleNamespace

import pytest

from src.cli.company_adjustment_commands import run_company_adjustment_command


def test_unknown_company_adjustment_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported company-adjustment command"):
        run_company_adjustment_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_amorepacific_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="audit-amorepacific-restructuring-v321",
        review_queue_csv=str(tmp_path / "missing.csv"),
        official_candidates_csv=str(tmp_path / "official.csv"),
        evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.95\]"):
        run_company_adjustment_command(SimpleNamespace(), args)
