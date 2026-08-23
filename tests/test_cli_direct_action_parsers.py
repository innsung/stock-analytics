import argparse

from src.cli.direct_action_parsers import register_direct_action_parsers


def test_direct_action_parsers_register_commands_and_pipeline_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_direct_action_parsers(sub)

    assert len(sub.choices) == 6
    inventory = parser.parse_args(["build-direct-action-document-inventory-v321"])
    assert inventory.documents_dir.endswith("direct_action_documents_phase561")
    route = parser.parse_args(["route-actionable-resolution-backlog-v321"])
    assert route.actionable_output_csv.endswith("actionable_resolution_queue_phase566_v321.csv")
    assert route.blocked_output_csv.endswith("blocked_resolution_queue_phase566_v321.csv")
