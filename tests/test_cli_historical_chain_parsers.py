import argparse

from src.cli.historical_chain_parsers import register_historical_chain_parsers


def test_historical_chain_parsers_register_commands_and_pipeline_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_historical_chain_parsers(sub)

    assert len(sub.choices) == 4
    quarantine = parser.parse_args(["quarantine-periodic-dividend-aggregates-v321"])
    assert quarantine.replacement_queue_csv.endswith("discrete_dividend_reconstruction_queue_phase583_v321.csv")
    validation = parser.parse_args(["validate-historical-chain-documents-v321"])
    assert validation.documents_dir.endswith("historical_chain_documents_phase585")
    consolidation = parser.parse_args(["consolidate-historical-legal-chains-v321"])
    assert consolidation.group_output_csv.endswith("historical_legal_event_groups_phase586_v321.csv")
