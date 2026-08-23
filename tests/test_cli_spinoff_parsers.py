import argparse

from src.cli.spinoff_parsers import register_spinoff_parsers


def test_spinoff_parsers_register_commands_and_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_spinoff_parsers(sub)

    assert len(sub.choices) == 5
    evidence = parser.parse_args(["audit-spinoff-evidence-completeness-v321"])
    assert evidence.document_path.endswith("corporate_action_documents_phase552/20250822000109.xml")
    gate = parser.parse_args(["build-complex-action-coverage-gate-v321"])
    assert gate.output_json.endswith("total_return_coverage_guarded_phase553_v321.json")
