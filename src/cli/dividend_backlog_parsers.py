from __future__ import annotations


def register_dividend_backlog_parsers(sub) -> None:
    p = sub.add_parser("defer-non-pit-dividends-v321")
    p.add_argument("--actionable-queue-csv", default="data/raw/v321/events/actionable_resolution_queue_phase579_v321.csv")
    p.add_argument("--residual-csv", default="data/raw/v321/events/residual_dividend_backlog_phase579_v321.csv")
    p.add_argument("--provenance-audit-csv", default="data/raw/v321/events/pre_exdate_provenance_audit_phase578_v321.csv")
    p.add_argument("--actionable-output-csv", default="data/raw/v321/events/actionable_resolution_queue_phase580_v321.csv")
    p.add_argument("--deferred-output-csv", default="data/raw/v321/events/deferred_non_pit_dividends_phase580_v321.csv")
    p.add_argument("--audit-output-csv", default="data/raw/v321/events/non_pit_dividend_deferral_audit_phase580_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/non_pit_dividend_deferral_summary_phase580_v321.json")
    p = sub.add_parser("resolve-recent-followups-v321")
    p.add_argument("--actionable-queue-csv", default="data/raw/v321/events/actionable_resolution_queue_phase580_v321.csv")
    p.add_argument("--resolved-verification-csv", default="data/raw/v321/events/event_verification_resolved_phase579_v321.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/recent_followup_documents_phase581")
    p.add_argument("--evidence-output-csv", default="data/raw/v321/events/recent_followup_not_applicable_evidence_phase581_v321.csv")
    p.add_argument("--audit-output-csv", default="data/raw/v321/events/recent_followup_resolution_audit_phase581_v321.csv")
    p = sub.add_parser("route-historical-backlog-v321")
    p.add_argument("--actionable-queue-csv", default="data/raw/v321/events/actionable_resolution_queue_phase581_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/historical_backlog_execution_summary_phase582_v321.json")
