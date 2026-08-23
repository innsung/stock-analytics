from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.market_effective_date_v321 import PykrxMarketAdjustmentProvider
from src.ml.phase611_naver_line_overseas_delisting_v321 import audit_naver_line_overseas_delisting_v321
from src.ml.phase612_historical_administrative_trading_halts_v321 import audit_historical_administrative_trading_halts_v321
from src.ml.phase613_related_party_rights_participation_v321 import audit_related_party_rights_participation_v321


COMMAND_SPECS = {
    "audit-naver-line-overseas-delisting-v321": ("6.11", "NAVER LINE Overseas Delisting"),
    "audit-historical-administrative-trading-halts-v321": ("6.12", "Historical Administrative Trading Halts"),
    "audit-related-party-rights-participation-v321": ("6.13", "Related-party Rights Participation"),
}


def run_market_followup_audit_command(settings, args) -> None:
    if args.command not in COMMAND_SPECS:
        raise ValueError(f"Unsupported market-followup audit command: {args.command}")

    phase, label = COMMAND_SPECS[args.command]
    kwargs = {
        "actionable_queue_csv": args.actionable_queue_csv,
        "disclosures_csv": args.disclosures_csv,
        "documents_dir": args.documents_dir,
        "evidence_output_csv": args.evidence_output_csv,
        "audit_output_csv": args.audit_output_csv,
        "summary_json": args.summary_json,
    }
    try:
        client = DartClient(settings.dart_api_key)
        if args.command == "audit-naver-line-overseas-delisting-v321":
            result = audit_naver_line_overseas_delisting_v321(
                client, PykrxMarketAdjustmentProvider(), **kwargs
            )
        elif args.command == "audit-historical-administrative-trading-halts-v321":
            result = audit_historical_administrative_trading_halts_v321(client, **kwargs)
        else:
            result = audit_related_party_rights_participation_v321(client, **kwargs)
    except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
        raise SystemExit(f"[V3.2.1 Phase {phase}] {exc}")

    print(f"[V3.2.1 Phase {phase} {label}]")
    print(f"Targets: {result['target_rows']:,}")
    print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
    print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")
