import argparse

import pytest

from src import main as app_main
from src.cli.command_dispatcher import ALL_COMMAND_INDEX


class _ParserCaptured(Exception):
    pass


def test_parser_and_dispatch_registry_commands_match_exactly(monkeypatch):
    captured = {}

    def capture_parser(parser, *args, **kwargs):
        captured["parser"] = parser
        raise _ParserCaptured

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture_parser)

    with pytest.raises(_ParserCaptured):
        app_main.main()

    parser = captured["parser"]
    subparsers_action = parser._subparsers._group_actions[0]
    parser_commands = set(subparsers_action.choices)
    dispatch_commands = set(ALL_COMMAND_INDEX)

    assert len(parser_commands) == 179
    assert parser_commands == dispatch_commands
