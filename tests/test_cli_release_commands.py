from types import SimpleNamespace

import pytest

from src.cli.release_commands import run_release_command


def test_release_dispatch_rejects_unknown_command():
    with pytest.raises(ValueError, match="지원하지 않는 릴리스 명령"):
        run_release_command(SimpleNamespace(command="unknown"))


def test_release_quality_gate_reports_missing_inputs(tmp_path):
    args = SimpleNamespace(
        command="build-release-quality-gate-v321",
        verification_csv=str(tmp_path / "missing-verification.csv"),
        actionable_csv=str(tmp_path / "missing-actionable.csv"),
        deferred_csv=str(tmp_path / "missing-deferred.csv"),
        blocked_csv=str(tmp_path / "missing-blocked.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match="Phase 6.26"):
        run_release_command(args)
