import argparse

from src.cli.primary_adjustment_parsers import register_primary_adjustment_parsers


def test_primary_adjustment_parsers_register_commands_and_pipeline_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_primary_adjustment_parsers(sub)

    assert len(sub.choices) == 3
    extraction = parser.parse_args(["extract-primary-adjustment-document-terms-v321"])
    assert extraction.review_queue_csv.endswith("primary_adjustment_document_review_phase587_v321.csv")
    validation = parser.parse_args(["validate-primary-adjustment-market-dates-v321"])
    assert validation.trading_calendar_db.endswith("stock_analytics_20260808_194044_baseline_v321.db")
    audit = parser.parse_args(["audit-historical-rights-applicability-v321"])
    assert audit.audit_output_csv.endswith("historical_rights_applicability_audit_phase589_v321.csv")
