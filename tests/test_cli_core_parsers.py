import argparse

import pytest

from src.cli.core_parsers import register_core_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_core_parsers(sub)
    return parser, sub


def test_core_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 6
    price = parser.parse_args(["collect-price", "005930"])
    assert price.days == 365
    backtest = parser.parse_args(["backtest", "005930"])
    assert backtest.capital == 10_000_000
    assert backtest.commission == .015
    walk_forward = parser.parse_args(["walk-forward", "005930"])
    assert walk_forward.train_years == 2
    assert walk_forward.test_months == 12
    robustness = parser.parse_args(["robustness", "005930"])
    assert robustness.simulations == 5000


def test_financial_collection_requires_year():
    parser, _ = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["collect-financial", "005930"])
