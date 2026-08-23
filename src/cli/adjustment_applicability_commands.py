from __future__ import annotations

import requests

from src.ml.market_effective_date_v321 import PykrxMarketAdjustmentProvider
from src.ml.phase590_merger_spinoff_applicability_v321 import audit_historical_merger_spinoff_applicability_v321
from src.ml.phase591_celltrion_merger_reparse_v321 import reparse_celltrion_merger_v321
from src.ml.phase592_capital_reduction_applicability_v321 import audit_historical_capital_reductions_v321
from src.ml.phase593_incomplete_primary_applicability_v321 import audit_incomplete_primary_adjustments_v321


ADJUSTMENT_APPLICABILITY_COMMANDS = frozenset(
    {
        "audit-historical-merger-spinoff-applicability-v321",
        "reparse-celltrion-merger-v321",
        "audit-historical-capital-reductions-v321",
        "audit-incomplete-primary-adjustments-v321",
    }
)


def run_adjustment_applicability_command(args) -> None:
    if args.command not in ADJUSTMENT_APPLICABILITY_COMMANDS:
        raise ValueError(f"Unsupported adjustment-applicability command: {args.command}")

    if args.command == "audit-historical-merger-spinoff-applicability-v321":
        try:
            result = audit_historical_merger_spinoff_applicability_v321(
                terms_csv=args.terms_csv,
                execution_manifest_csv=args.execution_manifest_csv,
                documents_dir=args.documents_dir,
                trading_calendar_db=args.trading_calendar_db,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.90] {exc}")
        print("[V3.2.1 Phase 5.90 Merger/Spinoff Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Material or reparse: {result['material_or_reparse_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "reparse-celltrion-merger-v321":
        try:
            result = reparse_celltrion_merger_v321(
                PykrxMarketAdjustmentProvider(),
                applicability_audit_csv=args.applicability_audit_csv,
                terms_csv=args.terms_csv,
                official_candidates_csv=args.official_candidates_csv,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.91] {exc}")
        print("[V3.2.1 Phase 5.91 Celltrion Merger Reparse]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-historical-capital-reductions-v321":
        try:
            result = audit_historical_capital_reductions_v321(
                terms_csv=args.terms_csv,
                execution_manifest_csv=args.execution_manifest_csv,
                documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.92] {exc}")
        print("[V3.2.1 Phase 5.92 Capital Reduction Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Listed reduction review: {result['listed_reduction_review_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    else:
        try:
            result = audit_incomplete_primary_adjustments_v321(
                terms_csv=args.terms_csv,
                execution_manifest_csv=args.execution_manifest_csv,
                documents_dir=args.documents_dir,
                trading_calendar_db=args.trading_calendar_db,
                evidence_output_csv=args.evidence_output_csv,
                review_output_csv=args.review_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.93] {exc}")
        print("[V3.2.1 Phase 5.93 Incomplete Primary Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Direct reparse: {result['direct_reparse_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
