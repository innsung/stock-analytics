from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.market_effective_date_v321 import PykrxMarketAdjustmentProvider
from src.ml.phase597_lgchem_subsidiary_rights_v321 import audit_lgchem_subsidiary_rights_v321
from src.ml.phase598_hdhyundai_exchangeable_bond_v321 import audit_hdhyundai_exchangeable_bond_v321
from src.ml.phase599_ecoprobm_merger_transfer_v321 import audit_ecoprobm_merger_transfer_v321


COMPANY_APPLICABILITY_COMMANDS = frozenset(
    {
        "audit-lgchem-subsidiary-rights-v321",
        "audit-hdhyundai-exchangeable-bond-v321",
        "audit-ecoprobm-merger-transfer-v321",
    }
)


def run_company_applicability_command(settings, args) -> None:
    if args.command not in COMPANY_APPLICABILITY_COMMANDS:
        raise ValueError(f"Unsupported company-applicability command: {args.command}")

    try:
        if args.command == "audit-lgchem-subsidiary-rights-v321":
            result = audit_lgchem_subsidiary_rights_v321(
                DartClient(settings.dart_api_key),
                actionable_queue_csv=args.actionable_queue_csv,
                disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
            phase = "5.97"
            label = "LG Chem Subsidiary Rights Applicability"
        elif args.command == "audit-hdhyundai-exchangeable-bond-v321":
            result = audit_hdhyundai_exchangeable_bond_v321(
                DartClient(settings.dart_api_key),
                PykrxMarketAdjustmentProvider(),
                actionable_queue_csv=args.actionable_queue_csv,
                documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
            phase = "5.98"
            label = "HD Hyundai Exchangeable Bond Applicability"
        else:
            result = audit_ecoprobm_merger_transfer_v321(
                DartClient(settings.dart_api_key),
                PykrxMarketAdjustmentProvider(),
                actionable_queue_csv=args.actionable_queue_csv,
                documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
            phase = "5.99"
            label = "Ecopro BM Merger and Transfer Applicability"
    except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
        phase_by_command = {
            "audit-lgchem-subsidiary-rights-v321": "5.97",
            "audit-hdhyundai-exchangeable-bond-v321": "5.98",
            "audit-ecoprobm-merger-transfer-v321": "5.99",
        }
        raise SystemExit(f"[V3.2.1 Phase {phase_by_command[args.command]}] {exc}")

    print(f"[V3.2.1 Phase {phase} {label}]")
    print(f"Targets: {result['target_rows']:,}")
    print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
    print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")
