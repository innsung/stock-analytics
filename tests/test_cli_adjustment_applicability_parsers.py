import argparse

from src.cli.adjustment_applicability_parsers import register_adjustment_applicability_parsers


def test_adjustment_applicability_parsers_register_commands_and_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_adjustment_applicability_parsers(sub)

    assert len(sub.choices) == 4
    merger = parser.parse_args(["audit-historical-merger-spinoff-applicability-v321"])
    assert merger.trading_calendar_db.endswith("stock_analytics_20260808_194044_baseline_v321.db")
    celltrion = parser.parse_args(["reparse-celltrion-merger-v321"])
    assert celltrion.audit_output_csv.endswith("celltrion_merger_reparse_audit_phase591_v321.csv")
    incomplete = parser.parse_args(["audit-incomplete-primary-adjustments-v321"])
    assert incomplete.review_output_csv.endswith("direct_primary_reparse_queue_phase593_v321.csv")
