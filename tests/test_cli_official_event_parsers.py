import argparse

import pytest

from src.cli.official_event_parsers import register_official_event_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_official_event_parsers(sub)
    return parser, sub


def test_official_event_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 6
    acquisition = parser.parse_args(["acquire-official-event-candidates-v321", "--universe-csv", "universe.csv"])
    assert acquisition.max_retries == 3
    assert acquisition.retry_backoff_seconds == 1.0
    market = parser.parse_args(["build-market-adjustment-evidence-v321", "--official-candidates-csv", "candidates.csv"])
    assert market.window_days == 20
    assert market.ratio_tolerance == .002


def test_strict_evidence_merge_accepts_repeated_inputs():
    parser, _ = _parser()
    args = parser.parse_args(
        ["merge-strict-evidence-v321", "--evidence-csv", "first.csv", "--evidence-csv", "second.csv"]
    )

    assert args.evidence_csv == ["first.csv", "second.csv"]


def test_official_event_preparation_requires_verification():
    parser, _ = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["prepare-official-event-evidence-v321"])
