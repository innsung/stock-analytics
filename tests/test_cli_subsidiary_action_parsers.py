import argparse

from src.cli.subsidiary_action_parsers import register_subsidiary_action_parsers


def test_subsidiary_action_parsers_register_commands_and_pipeline_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_subsidiary_action_parsers(sub)

    assert len(sub.choices) == 6
    acquire = parser.parse_args(["acquire-subsidiary-action-documents-v321"])
    assert acquire.documents_dir.endswith("subsidiary_action_documents_phase556")
    integrate = parser.parse_args(["integrate-residual-subsidiary-evidence-v321"])
    assert integrate.output_csv.endswith("event_verification_resolved_phase560_v321.csv")
    assert integrate.priority_output_csv.endswith("current_resolution_priority_phase560_v321.csv")
