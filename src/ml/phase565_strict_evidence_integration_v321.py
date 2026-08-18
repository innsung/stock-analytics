from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ml.official_event_resolver_v321 import read_official_event_evidence_v321
from src.ml.phase555_current_resolution_priority_v321 import prioritize_current_resolution_backlog_v321


def integrate_strict_event_evidence_v321(
    *, verification_csv: str, evidence_csv: str, output_csv: str,
    audit_csv: str, priority_output_csv: str, priority_summary_json: str,
) -> dict:
    verification = pd.read_csv(verification_csv, dtype=str).fillna("")
    evidence, valid, status = read_official_event_evidence_v321(evidence_csv)
    if not valid:
        bad = int((~evidence["row_valid"]).sum()) if not evidence.empty else 0
        raise ValueError(f"strict evidence invalid: {status}, invalid_rows={bad}")
    if evidence["queue_event_id"].str.strip().eq("").any():
        raise ValueError("strict evidence requires queue_event_id")
    if evidence["queue_event_id"].duplicated().any():
        raise ValueError("duplicate strict evidence queue_event_id")
    unknown = sorted(set(evidence["queue_event_id"]) - set(verification["queue_event_id"]))
    if unknown:
        raise ValueError("unknown strict evidence queue_event_id: " + ", ".join(unknown[:5]))
    out = verification.copy()
    audits = []
    for row in evidence.itertuples(index=False):
        mask = out["queue_event_id"].eq(row.queue_event_id)
        existing = set(out.loc[mask, "resolution_status"])
        if existing != {"UNRESOLVED"}:
            raise ValueError(f"strict evidence attempts to overwrite terminal status: {row.queue_event_id}")
        values = {
            "resolution_status": "VERIFIED", "effective_date": row.effective_date,
            "known_at": row.known_at, "action_type": row.action_type,
            "adjustment_factor": str(row.adjustment_factor), "cash_amount": str(row.cash_amount),
            "verification_source": row.verification_source,
            "verification_reference": row.verification_reference,
            "resolution_note": "INTEGRATED_STRICT_OFFICIAL_MARKET_EVIDENCE",
        }
        for column, value in values.items():
            out.loc[mask, column] = value
        audits.append({"queue_event_id": row.queue_event_id, "previous_status": "UNRESOLVED",
                       "new_status": "VERIFIED", "action_type": row.action_type,
                       "effective_date": row.effective_date, "integration_status": "APPLIED_STRICT_EVIDENCE"})
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    ap = Path(audit_csv); ap.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    priority = prioritize_current_resolution_backlog_v321(
        resolved_verification_csv=str(path), output_csv=priority_output_csv,
        summary_json=priority_summary_json, phase_label="V3.2.1 Phase 5.65")
    counts = out.drop_duplicates("queue_event_id")["resolution_status"].value_counts()
    return {"applied_rows": len(audits), "verified_queue_events": int(counts.get("VERIFIED", 0)),
            "not_applicable_queue_events": int(counts.get("NOT_APPLICABLE", 0)),
            "unresolved_queue_events": int(counts.get("UNRESOLVED", 0)),
            "next_target": priority["next_target"], "next_target_rows": priority["next_target_rows"],
            "output_csv": str(path), "audit_csv": str(ap),
            "priority_output_csv": priority["output_csv"], "priority_summary_json": priority["summary_json"]}
