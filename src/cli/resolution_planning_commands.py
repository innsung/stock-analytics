from __future__ import annotations

from src.ml.phase531_resolution_gap_prioritizer_v321 import prioritize_resolution_gaps_v321
from src.ml.phase532_recent_dividend_acquisition_manifest_v321 import build_recent_dividend_acquisition_manifest_v321
from src.ml.phase536_company_name_recovery_v321 import recover_acquisition_company_names_v321


COMMANDS = {
    "prioritize-resolution-gaps-v321",
    "build-recent-dividend-acquisition-manifest-v321",
    "recover-acquisition-company-names-v321",
}


def run_resolution_planning_command(args) -> None:
    if args.command not in COMMANDS:
        raise ValueError(f"Unsupported resolution-planning command: {args.command}")
    if args.command == "prioritize-resolution-gaps-v321":
        try:
            result = prioritize_resolution_gaps_v321(args.resolved_verification_csv, args.output_csv, args.summary_json)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.31] {exc}")
        print("[V3.2.1 Phase 5.31 Resolution Gap Prioritizer]")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Priority counts: {result['priority_counts']}")
        print(f"Next target: {result['next_target']}")
        print(f"Output: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "build-recent-dividend-acquisition-manifest-v321":
        try:
            result = build_recent_dividend_acquisition_manifest_v321(
                args.priority_queue_csv, args.decision_disclosures_csv,
                args.strict_evidence_csv, args.output_csv, args.summary_json)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.32] {exc}")
        print("[V3.2.1 Phase 5.32 Recent Dividend Acquisition Manifest]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    else:
        try:
            result = recover_acquisition_company_names_v321(
                args.acquisition_manifest_csv, args.dividend_facts_csv, args.output_csv, args.audit_csv)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.36] {exc}")
        print("[V3.2.1 Phase 5.36 Company Name Recovery]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Recovered names: {result['recovered_names']:,}")
        print(f"Remaining missing: {result['remaining_missing']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
