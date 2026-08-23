import argparse

from src.cli.dividend_backlog_parsers import register_dividend_backlog_parsers


def test_dividend_backlog_parsers_register_commands_and_pipeline_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_dividend_backlog_parsers(sub)

    assert len(sub.choices) == 3
    deferred = parser.parse_args(["defer-non-pit-dividends-v321"])
    assert deferred.actionable_output_csv.endswith("actionable_resolution_queue_phase580_v321.csv")
    assert deferred.deferred_output_csv.endswith("deferred_non_pit_dividends_phase580_v321.csv")
    followups = parser.parse_args(["resolve-recent-followups-v321"])
    assert followups.documents_dir.endswith("recent_followup_documents_phase581")
    routed = parser.parse_args(["route-historical-backlog-v321"])
    assert routed.output_csv.endswith("historical_backlog_execution_manifest_phase582_v321.csv")
