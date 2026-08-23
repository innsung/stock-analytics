from __future__ import annotations


def register_historical_dividend_parsers(sub) -> None:
    p = sub.add_parser("build-recent-dividend-evidence-inventory-v321")
    p.add_argument("--actionable-queue-csv", default="data/raw/v321/events/actionable_resolution_queue_phase566_v321.csv")
    p.add_argument("--prior-coverage-audit-csv", default="data/raw/v321/events/market_notice_coverage_audit_phase542_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/recent_dividend_evidence_inventory_phase567_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/recent_dividend_evidence_inventory_summary_phase567_v321.json")
    p = sub.add_parser("acquire-historical-dividend-decisions-v321")
    p.add_argument("--inventory-csv", default="data/raw/v321/events/recent_dividend_evidence_inventory_phase567_v321.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/historical_dividend_decisions_phase568")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_dividend_decision_acquisition_phase568_v321.csv")
    p = sub.add_parser("parse-historical-dividend-decisions-v321")
    p.add_argument("--acquisition-csv", default="data/raw/v321/events/historical_dividend_decision_acquisition_phase568_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_dividend_decision_parsed_phase569_v321.csv")
    p = sub.add_parser("build-historical-dividend-exdate-candidates-v321")
    p.add_argument("--parsed-csv", default="data/raw/v321/events/historical_dividend_decision_parsed_phase569_v321.csv")
    p.add_argument("--trading-calendar-db", default="data/backup/stock_analytics_20260808_194044_baseline_v321.db")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_dividend_exdate_candidates_phase570_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/historical_dividend_exdate_candidates_summary_phase570_v321.json")
