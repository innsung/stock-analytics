from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.market_effective_date_v321 import PykrxMarketAdjustmentProvider
from src.ml.phase587_primary_adjustment_document_terms_v321 import extract_primary_adjustment_document_terms_v321
from src.ml.phase588_primary_adjustment_market_validation_v321 import validate_primary_adjustment_market_dates_v321
from src.ml.phase589_rights_applicability_audit_v321 import audit_historical_rights_applicability_v321


PRIMARY_ADJUSTMENT_COMMANDS = frozenset(
    {
        "extract-primary-adjustment-document-terms-v321",
        "validate-primary-adjustment-market-dates-v321",
        "audit-historical-rights-applicability-v321",
    }
)


def run_primary_adjustment_command(settings, args) -> None:
    if args.command not in PRIMARY_ADJUSTMENT_COMMANDS:
        raise ValueError(f"Unsupported primary-adjustment command: {args.command}")

    if args.command == "extract-primary-adjustment-document-terms-v321":
        try:
            result = extract_primary_adjustment_document_terms_v321(
                DartClient(settings.dart_api_key),
                execution_manifest_csv=args.execution_manifest_csv,
                disclosures_csv=args.disclosures_csv,
                legal_groups_csv=args.legal_groups_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
                review_queue_csv=args.review_queue_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.87] {exc}")
        print("[V3.2.1 Phase 5.87 Primary Adjustment Document Terms]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Selected receipts: {result['selected_receipt_rows']:,}")
        print(f"Unique documents: {result['unique_documents_processed']:,}")
        print(f"Terms extracted: {result['terms_extracted_rows']:,}")
        print(f"Review rows: {result['review_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "validate-primary-adjustment-market-dates-v321":
        try:
            result = validate_primary_adjustment_market_dates_v321(
                PykrxMarketAdjustmentProvider(),
                terms_csv=args.terms_csv,
                execution_manifest_csv=args.execution_manifest_csv,
                trading_calendar_db=args.trading_calendar_db,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.88] {exc}")
        print("[V3.2.1 Phase 5.88 Primary Adjustment Market Validation]")
        print(f"Candidates: {result['extracted_candidate_rows']:,}")
        print(f"PIT-valid: {result['pit_valid_rows']:,}")
        print(f"Safe market candidates: {result['safe_market_factor_candidates']:,}")
        print(f"Strict market evidence: {result['strict_market_evidence_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    else:
        try:
            result = audit_historical_rights_applicability_v321(
                terms_csv=args.terms_csv,
                execution_manifest_csv=args.execution_manifest_csv,
                documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.89] {exc}")
        print("[V3.2.1 Phase 5.89 Rights Applicability Audit]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Shareholder-rights TERP candidates: {result['shareholder_rights_terp_candidates']:,}")
        print(f"Unresolved allotment methods: {result['unresolved_allotment_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
