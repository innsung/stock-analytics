from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.phase623_ecoprobm_bonus_issue_verification_v321 import verify_ecoprobm_bonus_issue_v321
from src.ml.phase624_hd_ksoe_third_party_capital_v321 import audit_hd_ksoe_third_party_capital_v321
from src.ml.phase625_shinhan_neoplux_share_exchange_v321 import audit_shinhan_neoplux_share_exchange_v321


COMMANDS = {
    "verify-ecoprobm-bonus-issue-v321": ("6.23", verify_ecoprobm_bonus_issue_v321),
    "audit-hd-ksoe-third-party-capital-v321": ("6.24", audit_hd_ksoe_third_party_capital_v321),
    "audit-shinhan-neoplux-share-exchange-v321": ("6.25", audit_shinhan_neoplux_share_exchange_v321),
}


def run_final_company_audit_command(settings, args) -> None:
    if args.command not in COMMANDS:
        raise ValueError(f"Unsupported final company-audit command: {args.command}")
    phase, handler = COMMANDS[args.command]
    common = dict(
        actionable_queue_csv=args.actionable_queue_csv,
        disclosures_csv=args.disclosures_csv,
        documents_dir=args.documents_dir,
        evidence_output_csv=args.evidence_output_csv,
        audit_output_csv=args.audit_output_csv,
        summary_json=args.summary_json,
    )
    try:
        client = DartClient(settings.dart_api_key)
        if phase == "6.23":
            result = handler(client, trading_calendar_db=args.trading_calendar_db, **common)
            label = "Ecopro BM Bonus Issue"
        elif phase == "6.24":
            result = handler(client, **common)
            label = "HD KSOE Third-party Capital"
        else:
            result = handler(client, phase621_audit_csv=args.phase621_audit_csv, **common)
            label = "Shinhan-Neoplux Share Exchange"
    except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
        raise SystemExit(f"[V3.2.1 Phase {phase}] {exc}")
    print(f"[V3.2.1 Phase {phase} {label}]")
    print(f"Targets: {result['target_rows']:,}")
    if phase == "6.23":
        print(f"Strict evidence: {result['strict_evidence_rows']:,}")
        print(f"Effective date: {result['effective_date']}")
        print(f"Adjustment factor: {result['adjustment_factor']}")
    else:
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")
