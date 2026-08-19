from types import SimpleNamespace

import pytest

from src.cli.direct_action_commands import run_direct_action_command


def test_unknown_direct_action_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported direct-action command"):
        run_direct_action_command(SimpleNamespace(), SimpleNamespace(command="unknown"))


def test_inventory_missing_input_preserves_phase_context(tmp_path):
    settings = SimpleNamespace(dart_api_key="test")
    args = SimpleNamespace(
        command="build-direct-action-document-inventory-v321",
        priority_queue_csv=str(tmp_path / "missing.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"),
        prior_acquisition_csv=str(tmp_path / "prior.csv"),
        documents_dir=str(tmp_path / "documents"),
        output_csv=str(tmp_path / "output.csv"),
    )

    with pytest.raises(SystemExit, match=r"\[V3\.2\.1 Phase 5\.61\]"):
        run_direct_action_command(settings, args)
