import argparse

import pytest

from src.cli.event_reconciliation_parsers import register_event_reconciliation_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_event_reconciliation_parsers(sub)
    return parser, sub


def test_event_reconciliation_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 5
    acquisition = parser.parse_args(["acquire-payout-actions-v321", "--universe-csv", "universe.csv"])
    assert (acquisition.start_year, acquisition.end_year) == (2020, 2026)
    assert acquisition.max_retries == 3
    total_return = parser.parse_args(["build-total-return-v321"])
    assert total_return.benchmark_code == "069500"
    finalization = parser.parse_args(
        ["finalize-event-reconciliation-v321", "--verification-csv", "verification.csv", "--queue-registry-csv", "registry.csv"]
    )
    assert finalization.coverage_start == "20200101"
    assert finalization.coverage_end == "20260709"


def test_event_reconciliation_requires_both_fact_sources():
    parser, _ = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["build-event-reconciliation-v321"])
