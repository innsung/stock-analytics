import argparse

from src.cli.dividend_resolution_parsers import register_dividend_resolution_parsers


def test_dividend_resolution_parsers_register_commands_and_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_dividend_resolution_parsers(sub)

    assert len(sub.choices) == 4
    ambiguous = parser.parse_args(["resolve-ambiguous-kind-notice-v321"])
    assert ambiguous.timeout_seconds == 20
    recovery = parser.parse_args(["recover-pre-exdate-dividend-evidence-v321"])
    assert recovery.strict_evidence_csv.endswith("pre_exdate_strict_evidence_phase578_v321.csv")
    no_dividend = parser.parse_args(["resolve-explicit-no-dividend-v321"])
    assert no_dividend.business_year == "2024"
