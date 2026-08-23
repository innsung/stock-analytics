import argparse

import pytest

from src.cli.kind_parsers import register_kind_parsers


def test_kind_parsers_register_commands_and_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_kind_parsers(sub)

    assert len(sub.choices) == 5
    retry = parser.parse_args(["retry-kind-dividends-v321", "--dry-run"])
    assert retry.timeout_seconds == 15
    assert retry.dry_run is True
    acquisition = parser.parse_args(["acquire-kind-market-exdates-v321"])
    assert acquisition.timeout_seconds == 20


def test_kind_crosscheck_requires_market_queue():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_kind_parsers(sub)

    with pytest.raises(SystemExit):
        parser.parse_args(["crosscheck-kind-dividends-v321"])
