from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.phase614_samsung_heavy_rights_price_followups_v321 import audit_samsung_heavy_rights_price_followups_v321
from src.ml.phase615_asset_transfer_completion_reports_v321 import audit_asset_transfer_completion_reports_v321
from src.ml.phase616_physical_split_business_transfer_completions_v321 import audit_physical_split_business_transfer_completions_v321


COMMAND_SPECS = {
    "audit-samsung-heavy-rights-price-followups-v321": ("6.14", "Samsung Heavy Rights Price Follow-ups"),
    "audit-asset-transfer-completion-reports-v321": ("6.15", "Asset-transfer Completion Reports"),
    "audit-physical-split-business-transfer-completions-v321": (
        "6.16",
        "Physical-split and Business-transfer Completions",
    ),
}


def run_completion_followup_command(settings, args) -> None:
    if args.command not in COMMAND_SPECS:
        raise ValueError(f"Unsupported completion-followup command: {args.command}")

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
        if args.command == "audit-samsung-heavy-rights-price-followups-v321":
            result = audit_samsung_heavy_rights_price_followups_v321(
                client,
                phase594_audit_csv=args.phase594_audit_csv,
                **kwargs,
            )
        elif args.command == "audit-asset-transfer-completion-reports-v321":
            result = audit_asset_transfer_completion_reports_v321(client, **kwargs)
        else:
            result = audit_physical_split_business_transfer_completions_v321(client, **kwargs)
    except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
        raise SystemExit(f"[V3.2.1 Phase {phase}] {exc}")

    print(f"[V3.2.1 Phase {phase} {label}]")
    print(f"Targets: {result['target_rows']:,}")
    print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
    print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")
