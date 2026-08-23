import argparse

import pytest

from src.cli.stock_dividend_evidence_parsers import register_stock_dividend_evidence_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_stock_dividend_evidence_parsers(sub)
    return parser, sub


def test_stock_dividend_evidence_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 12
    acquisition = parser.parse_args(["acquire-stock-dividend-decisions-v321", "--universe-csv", "universe.csv"])
    assert acquisition.start == "20200101"
    assert acquisition.end == "20260709"
    calendar = parser.parse_args(["export-benchmark-calendar-v321"])
    assert calendar.benchmark_code == "069500"
    assert calendar.include_post_cutoff is False


def test_market_exdate_queue_requires_both_sources():
    parser, _ = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["build-market-exdate-verification-queue-v321"])
