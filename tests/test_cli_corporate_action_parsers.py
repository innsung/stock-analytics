import argparse

import pytest

from src.cli.corporate_action_parsers import register_corporate_action_parsers


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_corporate_action_parsers(sub)
    return parser


def test_corporate_action_parsers_register_all_commands():
    parser = _parser()

    assert len(parser._subparsers._group_actions[0].choices) == 7
    args = parser.parse_args(["parse-corporate-action-documents-v321"])
    assert args.output_csv.endswith("corporate_action_document_parsed_phase547_v321.csv")


def test_market_notice_coverage_accepts_repeated_discovery_files():
    parser = _parser()
    args = parser.parse_args(
        ["audit-market-notice-coverage-v321", "--discovery-csv", "first.csv", "--discovery-csv", "second.csv"]
    )

    assert args.discovery_csv == ["first.csv", "second.csv"]


def test_market_notice_coverage_requires_discovery_file():
    with pytest.raises(SystemExit):
        _parser().parse_args(["audit-market-notice-coverage-v321"])
