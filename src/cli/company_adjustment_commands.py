from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.market_effective_date_v321 import PykrxMarketAdjustmentProvider
from src.ml.phase594_samsung_heavy_rights_verification_v321 import verify_samsung_heavy_rights_v321
from src.ml.phase595_amorepacific_restructuring_v321 import audit_amorepacific_restructuring_v321
from src.ml.phase596_overseas_listing_delisting_v321 import audit_overseas_listing_delistings_v321


COMPANY_ADJUSTMENT_COMMANDS = frozenset(
    {
        "verify-samsung-heavy-rights-v321",
        "audit-amorepacific-restructuring-v321",
        "audit-overseas-listing-delistings-v321",
    }
)


def run_company_adjustment_command(settings, args) -> None:
    if args.command not in COMPANY_ADJUSTMENT_COMMANDS:
        raise ValueError(f"Unsupported company-adjustment command: {args.command}")

    if args.command == "verify-samsung-heavy-rights-v321":
        try:
            result = verify_samsung_heavy_rights_v321(
                DartClient(settings.dart_api_key),
                PykrxMarketAdjustmentProvider(),
                review_queue_csv=args.review_queue_csv,
                decision_documents_dir=args.decision_documents_dir,
                output_documents_dir=args.output_documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.94] {exc}")
        print("[V3.2.1 Phase 5.94 Samsung Heavy Rights Verification]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Strict evidence: {result['strict_evidence_rows']:,}")
        print(f"Effective date: {result['effective_date']}")
        print(f"Adjustment factor: {result['adjustment_factor']}")
        print(f"Theoretical gap: {result['theoretical_gap']}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-amorepacific-restructuring-v321":
        try:
            result = audit_amorepacific_restructuring_v321(
                PykrxMarketAdjustmentProvider(),
                review_queue_csv=args.review_queue_csv,
                official_candidates_csv=args.official_candidates_csv,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.95] {exc}")
        _print_applicability("5.95 Amorepacific Restructuring Applicability", result)
    else:
        try:
            result = audit_overseas_listing_delistings_v321(
                DartClient(settings.dart_api_key),
                PykrxMarketAdjustmentProvider(),
                actionable_queue_csv=args.actionable_queue_csv,
                disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.96] {exc}")
        _print_applicability("5.96 Overseas Listing Delisting Applicability", result)


def _print_applicability(label: str, result: dict) -> None:
    print(f"[V3.2.1 Phase {label}]")
    print(f"Targets: {result['target_rows']:,}")
    print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
    print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")
