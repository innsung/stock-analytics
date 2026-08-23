import argparse

import pytest

from src.cli.ml_parsers import register_ml_parsers


def _parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_ml_parsers(sub)
    return parser, sub


def test_ml_parsers_register_commands_and_defaults():
    parser, sub = _parser()

    assert len(sub.choices) == 5
    readiness = parser.parse_args(["ml-readiness"])
    assert readiness.portfolio_id == "shadow_24_filtered"
    training = parser.parse_args(["ml-train"])
    assert training.horizon == 20
    assert training.validation_days == 126
    assert training.artifact == "models/baseline_h20.joblib"
    walk_forward = parser.parse_args(["ml-walk-forward"])
    assert walk_forward.min_train_days == 504


def test_ml_horizon_rejects_unsupported_value():
    parser, _ = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["ml-train", "--horizon", "10"])
