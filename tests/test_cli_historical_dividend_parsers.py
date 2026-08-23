import argparse

from src.cli.historical_dividend_parsers import register_historical_dividend_parsers


def test_historical_dividend_parsers_register_commands_and_pipeline_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_historical_dividend_parsers(sub)

    assert len(sub.choices) == 4
    acquisition = parser.parse_args(["acquire-historical-dividend-decisions-v321"])
    assert acquisition.documents_dir.endswith("historical_dividend_decisions_phase568")
    candidates = parser.parse_args(["build-historical-dividend-exdate-candidates-v321"])
    assert candidates.trading_calendar_db.endswith("stock_analytics_20260808_194044_baseline_v321.db")
    assert candidates.output_csv.endswith("historical_dividend_exdate_candidates_phase570_v321.csv")
