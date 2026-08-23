import argparse

import pytest

from src.cli.cash_distribution_parsers import register_cash_distribution_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_cash_distribution_parsers(sub)
    return parser, sub


def test_cash_distribution_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 7
    benchmark = parser.parse_args(["prepare-benchmark-etf-distributions-v321"])
    assert benchmark.code == "069500"
    comparison = parser.parse_args(
        ["compare-cash-amount-candidates-v321", "--strict-cash-evidence-csv", "strict.csv", "--amount-candidates-csv", "amount.csv"]
    )
    assert comparison.tolerance == 1e-9


def test_cash_candidates_require_source_files():
    parser, _ = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["build-stock-cash-amount-candidates-v321"])
