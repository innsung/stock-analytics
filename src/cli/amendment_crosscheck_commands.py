from __future__ import annotations

from src.ml.phase620_kakao_split_amendments_v321 import audit_kakao_split_amendments_v321
from src.ml.phase621_historical_amendment_duplicates_v321 import audit_historical_amendment_duplicates_v321
from src.ml.phase622_ecoprobm_rights_support_disclosures_v321 import audit_ecoprobm_rights_support_disclosures_v321


COMMAND_SPECS = {
    "audit-kakao-split-amendments-v321": ("6.20", "Kakao Split Amendments"),
    "audit-historical-amendment-duplicates-v321": ("6.21", "Historical Amendment Duplicates"),
    "audit-ecoprobm-rights-support-disclosures-v321": ("6.22", "Ecopro BM Rights Support Disclosures"),
}


def run_amendment_crosscheck_command(args) -> None:
    if args.command not in COMMAND_SPECS:
        raise ValueError(f"Unsupported amendment-crosscheck command: {args.command}")

    phase, label = COMMAND_SPECS[args.command]
    common = {
        "actionable_queue_csv": args.actionable_queue_csv,
        "disclosures_csv": args.disclosures_csv,
        "evidence_output_csv": args.evidence_output_csv,
        "audit_output_csv": args.audit_output_csv,
        "summary_json": args.summary_json,
    }
    try:
        if args.command == "audit-kakao-split-amendments-v321":
            result = audit_kakao_split_amendments_v321(
                phase590_audit_csv=args.phase590_audit_csv,
                phase616_audit_csv=args.phase616_audit_csv,
                **common,
            )
        elif args.command == "audit-historical-amendment-duplicates-v321":
            result = audit_historical_amendment_duplicates_v321(
                chain_csv=args.chain_csv,
                verification_csv=args.verification_csv,
                **common,
            )
        else:
            result = audit_ecoprobm_rights_support_disclosures_v321(
                phase618_audit_csv=args.phase618_audit_csv,
                **common,
            )
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"[V3.2.1 Phase {phase}] {exc}")

    print(f"[V3.2.1 Phase {phase} {label}]")
    print(f"Targets: {result['target_rows']:,}")
    print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
    print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")
