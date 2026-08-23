import argparse

import pytest

from src.cli.kodex_distribution_parsers import register_kodex_distribution_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_kodex_distribution_parsers(sub)
    return parser, sub


def test_kodex_distribution_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 6
    acquisition = parser.parse_args(["acquire-kodex-distributions-v321"])
    assert acquisition.timeout_seconds == 30.0
    assert acquisition.url.endswith("view.do?id=2ETF01")
    probe = parser.parse_args(["rank-probe-kodex-endpoints-v321", "--candidate-csv", "candidates.csv"])
    assert probe.top_n == 25
    assert probe.timeout_seconds == 12.0


def test_refined_candidates_require_source_files():
    parser, _ = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["refine-stock-dividend-candidates-v321"])
