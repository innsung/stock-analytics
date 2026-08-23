import argparse

import pytest

from src.cli.shadow_parsers import register_shadow_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_shadow_parsers(sub)
    return parser, sub


def test_shadow_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 5
    shadow = parser.parse_args(["shadow-run"])
    assert shadow.capital == 100_000_000
    assert shadow.top_n == 10
    assert shadow.portfolio_id == "default"
    status = parser.parse_args(["daily-status"])
    assert status.limit == 10


def test_daily_shadow_requires_portfolio_id_and_preserves_flags():
    parser, _ = _parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["daily-shadow"])

    daily = parser.parse_args(["daily-shadow", "--portfolio-id", "paper", "--allow-before-close", "--force-refresh"])
    assert daily.top_n == 12
    assert daily.allow_before_close is True
    assert daily.force_refresh is True
