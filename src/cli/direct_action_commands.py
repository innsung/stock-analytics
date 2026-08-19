from __future__ import annotations

from src.dart.client import DartClient
from src.ml.phase561_direct_action_document_inventory_v321 import build_direct_action_document_inventory_v321
from src.ml.phase562_direct_action_group_review_v321 import review_direct_action_groups_v321
from src.ml.phase563_direct_action_integration_v321 import integrate_direct_action_evidence_v321
from src.ml.phase564_samsung_sdi_rights_verification_v321 import verify_samsung_sdi_rights_v321
from src.ml.phase565_strict_evidence_integration_v321 import integrate_strict_event_evidence_v321
from src.ml.phase566_actionable_backlog_router_v321 import route_actionable_resolution_backlog_v321


DIRECT_ACTION_COMMANDS = frozenset(
    {
        "build-direct-action-document-inventory-v321",
        "review-direct-action-groups-v321",
        "integrate-direct-action-evidence-v321",
        "verify-samsung-sdi-rights-v321",
        "integrate-strict-event-evidence-v321",
        "route-actionable-resolution-backlog-v321",
    }
)


def run_direct_action_command(settings, args) -> None:
    if args.command not in DIRECT_ACTION_COMMANDS:
        raise ValueError(f"Unsupported direct-action command: {args.command}")

    if args.command == "build-direct-action-document-inventory-v321":
        try:
            result = build_direct_action_document_inventory_v321(
                DartClient(settings.dart_api_key),
                priority_queue_csv=args.priority_queue_csv,
                disclosures_csv=args.disclosures_csv,
                prior_acquisition_csv=args.prior_acquisition_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.61] {exc}")
        print("[V3.2.1 Phase 5.61 Direct Action Document Inventory]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Reused: {result['reused_rows']:,}")
        print(f"Newly acquired: {result['acquired_rows']:,}")
        print(f"Group-covered without standalone file: {result['group_covered_rows']:,}")
        print(f"Usable: {result['usable_rows']:,}")
        print(f"Candidate legal events: {result['candidate_legal_event_groups']:,}")
        print(f"Inventory: {result['output_csv']}")
    elif args.command == "review-direct-action-groups-v321":
        try:
            result = review_direct_action_groups_v321(
                inventory_csv=args.inventory_csv,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                parsed_documents_csv=args.parsed_documents_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.62] {exc}")
        print("[V3.2.1 Phase 5.62 Direct Action Group Review]")
        print(f"Groups: {result['reviewed_groups']:,}")
        print(f"Rows: {result['reviewed_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Core unresolved: {result['core_unresolved_rows']:,}")
        print(f"Evidence: {result['evidence_output_csv']}")
        print(f"Audit: {result['audit_output_csv']}")
    elif args.command == "integrate-direct-action-evidence-v321":
        try:
            result = integrate_direct_action_evidence_v321(**_integration_args(args))
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.63] {exc}")
        _print_integration_result("5.63 Direct Action Integration", result)
    elif args.command == "verify-samsung-sdi-rights-v321":
        try:
            result = verify_samsung_sdi_rights_v321(
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.64] {exc}")
        print("[V3.2.1 Phase 5.64 Samsung SDI Rights Verification]")
        print(f"Evidence rows: {result['evidence_rows']:,}")
        print(f"Effective date: {result['effective_date']}")
        print(f"Adjustment factor: {result['adjustment_factor']:.12f}")
        print(f"Theoretical gap: {result['theoretical_gap']:.6%}")
        print(f"Evidence: {result['evidence_output_csv']}")
        print(f"Audit: {result['audit_output_csv']}")
    elif args.command == "integrate-strict-event-evidence-v321":
        try:
            result = integrate_strict_event_evidence_v321(**_integration_args(args))
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.65] {exc}")
        _print_integration_result("5.65 Strict Evidence Integration", result)
    else:
        try:
            result = route_actionable_resolution_backlog_v321(
                priority_queue_csv=args.priority_queue_csv,
                direct_action_audit_csv=args.direct_action_audit_csv,
                complex_evidence_audit_csv=args.complex_evidence_audit_csv,
                actionable_output_csv=args.actionable_output_csv,
                blocked_output_csv=args.blocked_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.66] {exc}")
        print("[V3.2.1 Phase 5.66 Actionable Backlog Router]")
        print(f"Actionable: {result['actionable_rows']:,}")
        print(f"Blocked: {result['blocked_rows']:,}")
        print(f"Next target: {result['next_actionable_target']} ({result['next_actionable_rows']:,})")
        print(f"Resolution status changed: {result['resolution_status_changed']}")
        print(f"Actionable queue: {result['actionable_output_csv']}")
        print(f"Blocked queue: {result['blocked_output_csv']}")


def _integration_args(args) -> dict:
    return {
        "verification_csv": args.verification_csv,
        "evidence_csv": args.evidence_csv,
        "output_csv": args.output_csv,
        "audit_csv": args.audit_csv,
        "priority_output_csv": args.priority_output_csv,
        "priority_summary_json": args.priority_summary_json,
    }


def _print_integration_result(label: str, result: dict) -> None:
    print(f"[V3.2.1 Phase {label}]")
    print(f"Applied: {result['applied_rows']:,}")
    print(f"VERIFIED: {result['verified_queue_events']:,}")
    print(f"NOT_APPLICABLE: {result['not_applicable_queue_events']:,}")
    print(f"UNRESOLVED: {result['unresolved_queue_events']:,}")
    print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
    print(f"Resolved queue: {result['output_csv']}")
