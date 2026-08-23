import argparse

from src.cli.kind_followup_parsers import register_kind_followup_parsers


def test_kind_followup_parsers_register_commands_and_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_kind_followup_parsers(sub)

    assert len(sub.choices) == 9
    args = parser.parse_args(["discover-kind-market-notices-batch-v321"])
    assert args.search_start == "20260101"
    assert args.search_end == "20260709"
    assert args.timeout_seconds == 20
