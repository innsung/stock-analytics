from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.phase580_non_pit_dividend_deferral_v321 import defer_non_pit_dividends_v321
from src.ml.phase581_recent_followup_resolution_v321 import resolve_recent_followups_v321
from src.ml.phase582_historical_backlog_router_v321 import build_historical_backlog_execution_manifest_v321


DIVIDEND_BACKLOG_COMMANDS = frozenset(
    {
        "defer-non-pit-dividends-v321",
        "resolve-recent-followups-v321",
        "route-historical-backlog-v321",
    }
)


def run_dividend_backlog_command(settings, args) -> None:
    if args.command not in DIVIDEND_BACKLOG_COMMANDS:
        raise ValueError(f"Unsupported dividend-backlog command: {args.command}")

    if args.command == "defer-non-pit-dividends-v321":
        try:
            result = defer_non_pit_dividends_v321(
                actionable_queue_csv=args.actionable_queue_csv,
                residual_csv=args.residual_csv,
                provenance_audit_csv=args.provenance_audit_csv,
                actionable_output_csv=args.actionable_output_csv,
                deferred_output_csv=args.deferred_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.80] {exc}")
        print("[V3.2.1 Phase 5.80 Non-PIT Dividend Deferral]")
        print(f"Deferred non-PIT rows: {result['deferred_non_pit_rows']:,}")
        print(f"Remaining actionable rows: {result['remaining_actionable_rows']:,}")
        print(
            f"Recent batch accounted: {result['recent_dividend_batch_accounted_rows']:,}/"
            f"{result['recent_dividend_batch_total']:,}"
        )
        print(f"Resolution status changed: {result['resolution_status_changed']}")
        print(f"Deferred queue: {result['deferred_output_csv']}")
    elif args.command == "resolve-recent-followups-v321":
        try:
            result = resolve_recent_followups_v321(
                DartClient(settings.dart_api_key),
                actionable_queue_csv=args.actionable_queue_csv,
                resolved_verification_csv=args.resolved_verification_csv,
                documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.81] {exc}")
        print("[V3.2.1 Phase 5.81 Recent Follow-up Resolution]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    else:
        try:
            result = build_historical_backlog_execution_manifest_v321(
                actionable_queue_csv=args.actionable_queue_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.82] {exc}")
        print("[V3.2.1 Phase 5.82 Historical Backlog Execution Router]")
        print(f"Historical backlog: {result['historical_backlog_rows']:,}")
        print(f"Accounted: {result['accounted_rows']:,}")
        print(f"Candidate clusters: {result['candidate_cluster_count']:,}")
        print(f"Next lane: {result['next_execution_lane']}")
        print(f"Output: {result['output_csv']}")
