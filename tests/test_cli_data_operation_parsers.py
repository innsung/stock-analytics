import argparse

import pytest

from src.cli.data_operation_parsers import register_data_operation_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_data_operation_parsers(sub)
    return parser, sub


def test_data_operation_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 6
    provider = parser.parse_args(["krx-provider-check-v321"])
    assert provider.code == "005930"
    assert provider.end == "20260709"
    acquisition = parser.parse_args(
        ["acquire-historical-data-v321", "--universe-csv", "universe.csv", "--start", "20200101"]
    )
    assert acquisition.frequency == "m"
    assert acquisition.max_retries == 3
    assert acquisition.no_resume is False
    backup = parser.parse_args(["backup-db-v321"])
    assert backup.output_dir == "data/backup"
    assert backup.label == "manual"


def test_historical_acquisition_requires_universe_and_start():
    parser, _ = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["acquire-historical-data-v321"])
