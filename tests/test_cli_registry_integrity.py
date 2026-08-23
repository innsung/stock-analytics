from types import SimpleNamespace

import pytest

import src.cli.parser_registry as parser_registry
from src.cli.command_dispatcher import ALL_COMMAND_INDEX
from src.cli.parser_registry import (
    PARSER_SPECS,
    ParserResolutionError,
    ParserSpec,
    build_parser,
    load_parser_registrar,
)


def test_parser_and_dispatch_registry_commands_match_exactly():
    parser = build_parser()
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


def test_parser_resolution_errors_identify_broken_spec(monkeypatch):
    missing_module = ParserSpec("src.cli.missing_parsers", "register_missing_parsers")
    monkeypatch.setattr(
        parser_registry,
        "import_module",
        lambda _name: (_ for _ in ()).throw(ModuleNotFoundError("missing")),
    )
    with pytest.raises(ParserResolutionError, match="Cannot import parser module"):
        load_parser_registrar(missing_module)

    missing_function = ParserSpec("src.cli.fake_parsers", "register_fake_parsers")
    monkeypatch.setattr(parser_registry, "import_module", lambda _name: SimpleNamespace(other=1))
    with pytest.raises(ParserResolutionError, match="register_fake_parsers not found"):
        load_parser_registrar(missing_function)

    monkeypatch.setattr(
        parser_registry,
        "import_module",
        lambda _name: SimpleNamespace(register_fake_parsers="not callable"),
    )
    with pytest.raises(ParserResolutionError, match="is not callable"):
        load_parser_registrar(missing_function)
