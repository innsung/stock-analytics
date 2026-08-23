from __future__ import annotations

from src.ml.phase617_amorepacific_attachment_followups_v321 import audit_amorepacific_attachment_followups_v321
from src.ml.phase618_rights_offering_followups_v321 import audit_rights_offering_followups_v321
from src.ml.phase619_hdhyundai_subsidiary_rights_amendments_v321 import audit_hdhyundai_subsidiary_rights_amendments_v321


COMMAND_SPECS = {
    "audit-amorepacific-attachment-followups-v321": ("6.17", "Amorepacific Attachment Follow-ups"),
    "audit-rights-offering-followups-v321": ("6.18", "Rights-offering Follow-ups"),
    "audit-hdhyundai-subsidiary-rights-amendments-v321": (
        "6.19",
        "HD Hyundai Subsidiary Rights Amendments",
    ),
}


def run_amendment_followup_command(args) -> None:
    if args.command not in COMMAND_SPECS:
        raise ValueError(f"Unsupported amendment-followup command: {args.command}")

    phase, label = COMMAND_SPECS[args.command]
    kwargs = {
        "actionable_queue_csv": args.actionable_queue_csv,
        "disclosures_csv": args.disclosures_csv,
        "evidence_output_csv": args.evidence_output_csv,
        "audit_output_csv": args.audit_output_csv,
        "summary_json": args.summary_json,
    }
    try:
        if args.command == "audit-amorepacific-attachment-followups-v321":
            result = audit_amorepacific_attachment_followups_v321(
                phase595_audit_csv=args.phase595_audit_csv,
                **kwargs,
            )
        elif args.command == "audit-rights-offering-followups-v321":
            result = audit_rights_offering_followups_v321(**kwargs)
        else:
            result = audit_hdhyundai_subsidiary_rights_amendments_v321(**kwargs)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"[V3.2.1 Phase {phase}] {exc}")

    print(f"[V3.2.1 Phase {phase} {label}]")
    print(f"Targets: {result['target_rows']:,}")
    print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
    print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")
