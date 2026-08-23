import argparse

from src.cli.historical_kind_parsers import register_historical_kind_parsers


def test_historical_kind_parsers_register_commands_and_pipeline_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_historical_kind_parsers(sub)

    assert len(sub.choices) == 4
    discovery = parser.parse_args(["discover-historical-kind-exdates-v321"])
    assert discovery.timeout_seconds == 20
    integration = parser.parse_args(["integrate-historical-dividend-evidence-v321"])
    assert integration.output_csv.endswith("event_verification_resolved_phase573_v321.csv")
    backlog = parser.parse_args(["build-residual-dividend-backlog-v321"])
    assert backlog.output_csv.endswith("residual_dividend_backlog_phase574_v321.csv")
