from __future__ import annotations

from src.dart.client import DartClient
from src.ml.phase567_recent_dividend_evidence_inventory_v321 import build_recent_dividend_evidence_inventory_v321
from src.ml.phase568_historical_dividend_decision_acquisition_v321 import acquire_historical_dividend_decisions_v321
from src.ml.phase569_historical_dividend_decision_parser_v321 import parse_historical_dividend_decisions_v321
from src.ml.phase570_historical_dividend_exdate_candidates_v321 import build_historical_dividend_exdate_candidates_v321


HISTORICAL_DIVIDEND_COMMANDS = frozenset(
    {
        "build-recent-dividend-evidence-inventory-v321",
        "acquire-historical-dividend-decisions-v321",
        "parse-historical-dividend-decisions-v321",
        "build-historical-dividend-exdate-candidates-v321",
    }
)

STRICT_EVIDENCE_FILES = (
    "data/raw/v321/events/kind_paired_market_strict_evidence_phase535_v321.csv",
    "data/raw/v321/events/kind_paired_market_strict_evidence_phase537_v321.csv",
    "data/raw/v321/events/kind_paired_market_strict_evidence_phase538_v321.csv",
    "data/raw/v321/events/kind_paired_market_strict_evidence_phase539_v321.csv",
    "data/raw/v321/events/kind_paired_market_strict_evidence_phase540_v321.csv",
    "data/raw/v321/events/kind_paired_market_strict_evidence_phase541_v321.csv",
)


def run_historical_dividend_command(settings, args) -> None:
    if args.command not in HISTORICAL_DIVIDEND_COMMANDS:
        raise ValueError(f"Unsupported historical-dividend command: {args.command}")

    if args.command == "build-recent-dividend-evidence-inventory-v321":
        try:
            result = build_recent_dividend_evidence_inventory_v321(
                actionable_queue_csv=args.actionable_queue_csv,
                prior_coverage_audit_csv=args.prior_coverage_audit_csv,
                strict_evidence_csvs=STRICT_EVIDENCE_FILES,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.67] {exc}")
        print("[V3.2.1 Phase 5.67 Recent Dividend Evidence Inventory]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Future non-linkable evidence rows: {result['future_non_linkable_rows']:,}")
        print(f"Auto-promoted: {result['auto_promoted_rows']:,}")
        print(f"Next target: {result['next_target']}")
        print(f"Inventory: {result['output_csv']}")
    elif args.command == "acquire-historical-dividend-decisions-v321":
        try:
            result = acquire_historical_dividend_decisions_v321(
                DartClient(settings.dart_api_key),
                inventory_csv=args.inventory_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.68] {exc}")
        print("[V3.2.1 Phase 5.68 Historical Dividend Decision Acquisition]")
        print(f"Targets: {result['target_queue_rows']:,}")
        print(f"Queue rows with candidates: {result['queue_rows_with_candidates']:,}")
        print(f"Documents acquired: {result['candidate_documents_acquired']:,}")
        print(f"Queue rows without candidates: {result['queue_rows_without_candidates']:,}")
        print(f"Manifest: {result['output_csv']}")
        print(f"Documents: {result['documents_dir']}")
    elif args.command == "parse-historical-dividend-decisions-v321":
        try:
            result = parse_historical_dividend_decisions_v321(
                acquisition_csv=args.acquisition_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.69] {exc}")
        print("[V3.2.1 Phase 5.69 Historical Dividend Decision Parser]")
        print(f"Manifest rows: {result['manifest_rows']:,}")
        print(f"Parsed rows: {result['parsed_rows']:,}")
        print(f"Incomplete rows: {result['incomplete_rows']:,}")
        print(f"Output: {result['output_csv']}")
    else:
        try:
            result = build_historical_dividend_exdate_candidates_v321(
                parsed_csv=args.parsed_csv,
                trading_calendar_db=args.trading_calendar_db,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.70] {exc}")
        print("[V3.2.1 Phase 5.70 Historical Dividend Ex-date Candidates]")
        print(f"Canonical parsed rows: {result['parsed_rows']:,}")
        print(f"Duplicate corrective filings removed: {result['deduplicated_rows']:,}")
        print(f"Ready for official market verification: {result['ready_for_market_verification']:,}")
        print(f"Late disclosure rows: {result['late_disclosure_rows']:,}")
        print(f"Strict rows: {result['strict_rows']:,}")
        print(f"Output: {result['output_csv']}")
