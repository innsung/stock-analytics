from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.market_effective_date_v321 import PykrxMarketAdjustmentProvider
from src.ml.phase600_kakao_zero_ratio_merger_v321 import audit_kakao_zero_ratio_merger_v321
from src.ml.phase601_celltrion_merger_followups_v321 import audit_celltrion_merger_followups_v321
from src.ml.phase602_kakao_overseas_dr_delisting_v321 import audit_kakao_overseas_dr_delisting_v321
from src.ml.phase603_samsung_heavy_preferred_delisting_warning_v321 import audit_samsung_heavy_preferred_delisting_warnings_v321


MERGER_FOLLOWUP_COMMANDS = frozenset(
    {
        "audit-kakao-zero-ratio-merger-v321",
        "audit-celltrion-merger-followups-v321",
        "audit-kakao-overseas-dr-delisting-v321",
        "audit-samsung-heavy-preferred-delisting-warnings-v321",
    }
)


def run_merger_followup_command(settings, args) -> None:
    if args.command not in MERGER_FOLLOWUP_COMMANDS:
        raise ValueError(f"Unsupported merger-followup command: {args.command}")

    phase, label = _metadata(args.command)
    common = {
        "actionable_queue_csv": args.actionable_queue_csv,
        "documents_dir": args.documents_dir,
        "evidence_output_csv": args.evidence_output_csv,
        "audit_output_csv": args.audit_output_csv,
        "summary_json": args.summary_json,
    }
    try:
        client = DartClient(settings.dart_api_key)
        if args.command == "audit-kakao-zero-ratio-merger-v321":
            result = audit_kakao_zero_ratio_merger_v321(client, PykrxMarketAdjustmentProvider(), **common)
        elif args.command == "audit-celltrion-merger-followups-v321":
            result = audit_celltrion_merger_followups_v321(
                client,
                phase591_audit_csv=args.phase591_audit_csv,
                **common,
            )
        elif args.command == "audit-kakao-overseas-dr-delisting-v321":
            result = audit_kakao_overseas_dr_delisting_v321(
                client,
                PykrxMarketAdjustmentProvider(),
                disclosures_csv=args.disclosures_csv,
                **common,
            )
        else:
            result = audit_samsung_heavy_preferred_delisting_warnings_v321(
                client,
                disclosures_csv=args.disclosures_csv,
                **common,
            )
    except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
        raise SystemExit(f"[V3.2.1 Phase {phase}] {exc}")

    print(f"[V3.2.1 Phase {phase} {label}]")
    print(f"Targets: {result['target_rows']:,}")
    print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
    print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")


def _metadata(command: str) -> tuple[str, str]:
    return {
        "audit-kakao-zero-ratio-merger-v321": ("6.00", "Kakao Zero-ratio Merger Applicability"),
        "audit-celltrion-merger-followups-v321": ("6.01", "Celltrion Merger Follow-up Consolidation"),
        "audit-kakao-overseas-dr-delisting-v321": ("6.02", "Kakao Overseas DR Delisting"),
        "audit-samsung-heavy-preferred-delisting-warnings-v321": (
            "6.03",
            "Samsung Heavy Preferred-share Delisting Warnings",
        ),
    }[command]
