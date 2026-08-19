from __future__ import annotations

from src.dart.client import DartClient
from src.ml.phase544_corporate_action_candidate_manifest_v321 import build_corporate_action_candidate_manifest_v321
from src.ml.phase545_market_adjustment_candidate_selector_v321 import select_market_adjustment_candidates_v321
from src.ml.phase546_corporate_action_document_acquisition_v321 import acquire_missing_corporate_action_documents_v321
from src.ml.phase547_corporate_action_document_parser_v321 import parse_corporate_action_documents_v321
from src.ml.phase548_complex_action_semantic_review_v321 import review_complex_corporate_actions_v321


CORPORATE_ACTION_DOCUMENT_COMMANDS = frozenset(
    {
        "build-corporate-action-candidate-manifest-v321",
        "select-market-adjustment-candidates-v321",
        "acquire-missing-corporate-action-documents-v321",
        "parse-corporate-action-documents-v321",
        "review-complex-corporate-actions-v321",
    }
)


def run_corporate_action_document_command(settings, args) -> None:
    if args.command not in CORPORATE_ACTION_DOCUMENT_COMMANDS:
        raise ValueError(f"Unsupported corporate-action document command: {args.command}")

    if args.command == "build-corporate-action-candidate-manifest-v321":
        try:
            result = build_corporate_action_candidate_manifest_v321(
                classified_queue_csv=args.classified_queue_csv,
                official_candidates_csv=args.official_candidates_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.44] {exc}")
        print("[V3.2.1 Phase 5.44 Corporate Action Candidate Manifest]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "select-market-adjustment-candidates-v321":
        try:
            result = select_market_adjustment_candidates_v321(
                candidate_manifest_csv=args.candidate_manifest_csv,
                official_candidates_csv=args.official_candidates_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.45] {exc}")
        print("[V3.2.1 Phase 5.45 Market Adjustment Candidate Selector]")
        print(f"Receipts: {result['manifest_receipts']:,}")
        print(f"Selected: {result['selected_candidates']:,}")
        print(f"Action counts: {result['action_counts']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "acquire-missing-corporate-action-documents-v321":
        try:
            result = acquire_missing_corporate_action_documents_v321(
                DartClient(settings.dart_api_key),
                candidate_manifest_csv=args.candidate_manifest_csv,
                disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.46] {exc}")
        print("[V3.2.1 Phase 5.46 Corporate Action Document Acquisition]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Acquired: {result['acquired_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Documents: {result['documents_dir']}")
    elif args.command == "parse-corporate-action-documents-v321":
        try:
            result = parse_corporate_action_documents_v321(
                acquisition_csv=args.acquisition_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.47] {exc}")
        print("[V3.2.1 Phase 5.47 Corporate Action Document Parser]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Parsed rows: {result['parsed_rows']:,}")
        print(f"Eligibility: {result['eligibility_counts']}")
        print(f"Output: {result['output_csv']}")
    else:
        try:
            result = review_complex_corporate_actions_v321(
                candidate_manifest_csv=args.candidate_manifest_csv,
                official_candidates_csv=args.official_candidates_csv,
                not_applicable_csv=args.not_applicable_csv,
                audit_csv=args.audit_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.48] {exc}")
        print("[V3.2.1 Phase 5.48 Complex Corporate Action Review]")
        print(f"Reviewed: {result['reviewed_rows']:,}")
        print(f"NOT_APPLICABLE: {result['not_applicable_rows']:,}")
        print(f"Complex unresolved: {result['complex_rows']:,}")
        print(f"Evidence: {result['not_applicable_csv']}")
        print(f"Audit: {result['audit_csv']}")
