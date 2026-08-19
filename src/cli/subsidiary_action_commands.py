from __future__ import annotations

from src.dart.client import DartClient
from src.ml.phase555_current_resolution_priority_v321 import prioritize_current_resolution_backlog_v321
from src.ml.phase556_subsidiary_document_acquisition_v321 import acquire_subsidiary_action_documents_v321
from src.ml.phase557_subsidiary_applicability_parser_v321 import parse_subsidiary_action_applicability_v321
from src.ml.phase558_not_applicable_integration_v321 import integrate_not_applicable_evidence_v321
from src.ml.phase559_residual_subsidiary_resolver_v321 import resolve_residual_subsidiary_actions_v321
from src.ml.phase560_residual_subsidiary_integration_v321 import integrate_residual_subsidiary_evidence_v321


SUBSIDIARY_ACTION_COMMANDS = frozenset(
    {
        "prioritize-current-resolution-backlog-v321",
        "acquire-subsidiary-action-documents-v321",
        "parse-subsidiary-action-applicability-v321",
        "integrate-not-applicable-evidence-v321",
        "resolve-residual-subsidiary-actions-v321",
        "integrate-residual-subsidiary-evidence-v321",
    }
)


def run_subsidiary_action_command(settings, args) -> None:
    if args.command not in SUBSIDIARY_ACTION_COMMANDS:
        raise ValueError(f"Unsupported subsidiary-action command: {args.command}")

    if args.command == "prioritize-current-resolution-backlog-v321":
        try:
            result = prioritize_current_resolution_backlog_v321(
                resolved_verification_csv=args.resolved_verification_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.55] {exc}")
        print("[V3.2.1 Phase 5.55 Current Resolution Priority]")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Next target: {result['next_target']}")
        print(f"Next target rows: {result['next_target_rows']:,}")
        print(f"Queue: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "acquire-subsidiary-action-documents-v321":
        try:
            result = acquire_subsidiary_action_documents_v321(
                DartClient(settings.dart_api_key),
                priority_queue_csv=args.priority_queue_csv,
                disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.56] {exc}")
        print("[V3.2.1 Phase 5.56 Subsidiary Action Document Acquisition]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Acquired: {result['acquired_rows']:,}")
        print(f"Ambiguous: {result['ambiguous_rows']:,}")
        print(f"Manifest: {result['output_csv']}")
        print(f"Documents: {result['documents_dir']}")
    elif args.command == "parse-subsidiary-action-applicability-v321":
        try:
            result = parse_subsidiary_action_applicability_v321(
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                audit_output_csv=args.audit_output_csv,
                not_applicable_output_csv=args.not_applicable_output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.57] {exc}")
        print("[V3.2.1 Phase 5.57 Subsidiary Action Applicability]")
        print(f"Reviewed: {result['reviewed_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Direct issuer review: {result['direct_issuer_review_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Audit: {result['audit_output_csv']}")
        print(f"Evidence: {result['not_applicable_output_csv']}")
    elif args.command == "integrate-not-applicable-evidence-v321":
        try:
            result = integrate_not_applicable_evidence_v321(
                verification_csv=args.verification_csv,
                evidence_csv=args.evidence_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                priority_output_csv=args.priority_output_csv,
                priority_summary_json=args.priority_summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.58] {exc}")
        _print_integration_result("5.58 NOT_APPLICABLE Integration", result)
    elif args.command == "resolve-residual-subsidiary-actions-v321":
        try:
            result = resolve_residual_subsidiary_actions_v321(
                DartClient(settings.dart_api_key),
                applicability_audit_csv=args.applicability_audit_csv,
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.59] {exc}")
        print("[V3.2.1 Phase 5.59 Residual Subsidiary Resolution]")
        print(f"Reviewed: {result['reviewed_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Evidence: {result['evidence_output_csv']}")
        print(f"Audit: {result['audit_output_csv']}")
    else:
        try:
            result = integrate_residual_subsidiary_evidence_v321(
                verification_csv=args.verification_csv,
                evidence_csv=args.evidence_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                priority_output_csv=args.priority_output_csv,
                priority_summary_json=args.priority_summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.60] {exc}")
        _print_integration_result("5.60 Residual Subsidiary Integration", result)


def _print_integration_result(label: str, result: dict) -> None:
    print(f"[V3.2.1 Phase {label}]")
    print(f"Applied: {result['applied_rows']:,}")
    print(f"VERIFIED: {result['verified_queue_events']:,}")
    print(f"NOT_APPLICABLE: {result['not_applicable_queue_events']:,}")
    print(f"UNRESOLVED: {result['unresolved_queue_events']:,}")
    print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
    print(f"Resolved queue: {result['output_csv']}")
