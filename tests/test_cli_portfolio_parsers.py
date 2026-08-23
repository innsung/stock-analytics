import argparse

import pytest

from src.cli.portfolio_parsers import register_portfolio_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_portfolio_parsers(sub)
    return parser, sub


def test_portfolio_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 7
    portfolio = parser.parse_args(["portfolio-verify", "005930"])
    assert portfolio.benchmark_code == "069500"
    assert portfolio.rebalance == "monthly"
    assert portfolio.stock_cap == .20
    assert portfolio.sector_cap == .35
    ranking = parser.parse_args(["rank-universe"])
    assert ranking.export_csv == "daily_ranking.csv"
    assert ranking.min_liquidity == 1_000_000_000


def test_external_verification_requires_codes():
    parser, _ = _parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["external-verify"])


def test_financial_series_requires_year_range():
    parser, _ = _parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["collect-financial-series"])
