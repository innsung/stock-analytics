import argparse

import pytest

from src import main as app_main
from src.cli.command_dispatcher import ALL_COMMAND_INDEX
from src.cli.parser_registry import PARSER_SPECS, ParserSpec, load_parser_registrar


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


def test_parser_registry_is_unique_complete_and_resolvable():
    assert len(PARSER_SPECS) == 26
    assert len(PARSER_SPECS) == len(set(PARSER_SPECS))
    assert all(isinstance(spec, ParserSpec) for spec in PARSER_SPECS)
    assert all(callable(load_parser_registrar(spec)) for spec in PARSER_SPECS)
