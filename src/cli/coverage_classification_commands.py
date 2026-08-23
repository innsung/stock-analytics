from __future__ import annotations

from src.ml.phase542_market_notice_coverage_audit_v321 import audit_market_notice_coverage_v321
from src.ml.phase543_recent_corporate_action_classifier_v321 import classify_recent_corporate_actions_v321


COMMANDS = {
    "audit-market-notice-coverage-v321",
    "classify-recent-corporate-actions-v321",
}


def run_coverage_classification_command(args) -> None:
    if args.command not in COMMANDS:
        raise ValueError(f"Unsupported coverage-classification command: {args.command}")

    if args.command == "audit-market-notice-coverage-v321":
        try:
            result = audit_market_notice_coverage_v321(
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                strict_evidence_csv=args.strict_evidence_csv,
                discovery_csvs=args.discovery_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.42] {exc}")
        print("[V3.2.1 Phase 5.42 Market Notice Coverage Audit]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Coverage: {result['coverage_counts']}")
    else:
        try:
            result = classify_recent_corporate_actions_v321(
                priority_queue_csv=args.priority_queue_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.43] {exc}")
        print("[V3.2.1 Phase 5.43 Recent Corporate Action Classifier]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Priority counts: {result['priority_counts']}")
        print(f"Direct issuer actions: {result['direct_issuer_action_rows']:,}")
    print(f"Output: {result['output_csv']}")
    print(f"Summary: {result['summary_json']}")
