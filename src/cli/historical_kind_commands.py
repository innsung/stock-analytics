from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.phase571_historical_kind_exdate_discovery_v321 import discover_historical_kind_exdates_v321
from src.ml.phase572_historical_kind_strict_evidence_v321 import build_historical_kind_strict_evidence_v321
from src.ml.phase573_historical_dividend_queue_integration_v321 import integrate_historical_dividend_evidence_v321
from src.ml.phase574_residual_dividend_backlog_v321 import build_residual_dividend_backlog_v321


HISTORICAL_KIND_COMMANDS = frozenset(
    {
        "discover-historical-kind-exdates-v321",
        "build-historical-kind-strict-evidence-v321",
        "integrate-historical-dividend-evidence-v321",
        "build-residual-dividend-backlog-v321",
    }
)


def run_historical_kind_command(settings, args) -> None:
    if args.command not in HISTORICAL_KIND_COMMANDS:
        raise ValueError(f"Unsupported historical-KIND command: {args.command}")

    if args.command == "discover-historical-kind-exdates-v321":
        try:
            result = discover_historical_kind_exdates_v321(
                DartClient(settings.dart_api_key),
                candidates_csv=args.candidates_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.71] {exc}")
        print("[V3.2.1 Phase 5.71 Historical KIND Ex-date Discovery]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Official notices discovered: {result['discovered_rows']:,}")
        print(f"Unmatched: {result['unmatched_rows']:,}")
        print(f"Ambiguous: {result['ambiguous_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "build-historical-kind-strict-evidence-v321":
        try:
            result = build_historical_kind_strict_evidence_v321(
                discovery_csv=args.discovery_csv,
                parsed_decisions_csv=args.parsed_decisions_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.72] {exc}")
        print("[V3.2.1 Phase 5.72 Historical KIND Strict Evidence]")
        print(f"Discovered notices: {result['discovered_rows']:,}")
        print(f"Strict evidence rows: {result['strict_rows']:,}")
        print(f"Invalid rows: {result['invalid_rows']:,}")
        print(f"Preferred-share rows: {result['preferred_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "integrate-historical-dividend-evidence-v321":
        try:
            result = integrate_historical_dividend_evidence_v321(
                verification_csv=args.verification_csv,
                strict_ledger_csv=args.strict_ledger_csv,
                selected_evidence_csv=args.selected_evidence_csv,
                selection_audit_csv=args.selection_audit_csv,
                output_csv=args.output_csv,
                integration_audit_csv=args.integration_audit_csv,
                priority_output_csv=args.priority_output_csv,
                priority_summary_json=args.priority_summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.73] {exc}")
        print("[V3.2.1 Phase 5.73 Historical Dividend Queue Integration]")
        print(f"Strict ledger rows: {result['strict_ledger_rows']:,}")
        print(f"Selected queue rows: {result['selected_queue_rows']:,}")
        print(f"Ledger-only historical rows: {result['ledger_only_rows']:,}")
        print(f"Verified: {result['verified_queue_events']:,}")
        print(f"Not applicable: {result['not_applicable_queue_events']:,}")
        print(f"Unresolved: {result['unresolved_queue_events']:,}")
        print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
        print(f"Output: {result['output_csv']}")
    else:
        try:
            result = build_residual_dividend_backlog_v321(
                actionable_queue_csv=args.actionable_queue_csv,
                acquisition_csv=args.acquisition_csv,
                candidates_csv=args.candidates_csv,
                discovery_audit_csv=args.discovery_audit_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.74] {exc}")
        print("[V3.2.1 Phase 5.74 Residual Dividend Backlog]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
        print(f"Resolution status changed: {result['resolution_status_changed']}")
        print(f"Output: {result['output_csv']}")
