from types import SimpleNamespace

import pytest

from src.cli.historical_chain_commands import run_historical_chain_command


def test_unknown_historical_chain_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported historical-chain command"):
        run_historical_chain_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_chain_build_missing_input_preserves_phase_context(tmp_path):
    args = SimpleNamespace(
        command="build-historical-legal-event-chain-v321",
        execution_manifest_csv=str(tmp_path / "missing.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"),
        output_csv=str(tmp_path / "output.csv"),
        review_queue_csv=str(tmp_path / "review.csv"),
        summary_json=str(tmp_path / "summary.json"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.84\]"):
        run_historical_chain_command(SimpleNamespace(), args)
