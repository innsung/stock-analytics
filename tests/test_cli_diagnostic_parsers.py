import argparse

import pytest

from src.cli.diagnostic_parsers import register_diagnostic_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_diagnostic_parsers(sub)
    return parser, sub


def test_diagnostic_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 3
    selfcheck = parser.parse_args(["phase516-selfcheck"])
    assert selfcheck.command == "phase516-selfcheck"
    diagnosis = parser.parse_args(["ml-diagnose-v321"])
    assert diagnosis.horizon == 20
    assert diagnosis.validation_days == 252
    assert diagnosis.min_train_days == 504
    assert diagnosis.rank_scope == "market"
    assert diagnosis.zip_results is False


def test_kodex_next_hops_requires_bodies_directory():
    parser, _ = _parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["discover-kodex-next-hops-v321"])


def test_ml_diagnosis_rejects_unsupported_rank_scope():
    parser, _ = _parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["ml-diagnose-v321", "--rank-scope", "sector"])
