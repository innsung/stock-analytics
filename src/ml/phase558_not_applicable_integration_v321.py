from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ml.phase555_current_resolution_priority_v321 import prioritize_current_resolution_backlog_v321


def integrate_not_applicable_evidence_v321(
    *, verification_csv: str, evidence_csv: str, output_csv: str,
    audit_csv: str, priority_output_csv: str, priority_summary_json: str,
    phase_label: str = "V3.2.1 Phase 5.58",
) -> dict:
    verification = pd.read_csv(verification_csv, dtype=str).fillna("")
    evidence = pd.read_csv(evidence_csv, dtype=str).fillna("")
    required_v = {"queue_event_id", "resolution_status", "verification_source",
                  "verification_reference", "resolution_note"}
    required_e = {"queue_event_id", "verification_source",
                  "verification_reference", "resolution_note"}
    if required_v - set(verification.columns):
        raise ValueError("verification CSV missing required columns")
    if required_e - set(evidence.columns):
        raise ValueError("NOT_APPLICABLE evidence missing required columns")
    if evidence["queue_event_id"].duplicated().any():
        raise ValueError("duplicate NOT_APPLICABLE evidence queue_event_id")
    if evidence[list(required_e)].apply(lambda col: col.str.strip().eq("")).any(axis=None):
        raise ValueError("blank required NOT_APPLICABLE evidence value")
    known = set(verification["queue_event_id"])
    unknown = sorted(set(evidence["queue_event_id"]) - known)
    if unknown:
        raise ValueError("unknown NOT_APPLICABLE queue_event_id: " + ", ".join(unknown[:5]))

    out = verification.copy()
    audit_rows = []
    for row in evidence.itertuples(index=False):
        mask = out["queue_event_id"].eq(row.queue_event_id)
        existing = set(out.loc[mask, "resolution_status"])
        if existing != {"UNRESOLVED"}:
            raise ValueError(f"evidence attempts to overwrite terminal status: {row.queue_event_id}")
        out.loc[mask, "resolution_status"] = "NOT_APPLICABLE"
        out.loc[mask, "verification_source"] = row.verification_source
        out.loc[mask, "verification_reference"] = row.verification_reference
        out.loc[mask, "resolution_note"] = row.resolution_note
        audit_rows.append({"queue_event_id": row.queue_event_id,
                           "previous_status": "UNRESOLVED", "new_status": "NOT_APPLICABLE",
                           "integration_status": "APPLIED_EXPLICIT_EVIDENCE"})
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    ap = Path(audit_csv); ap.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audit_rows).to_csv(ap, index=False, encoding="utf-8-sig")
    priority = prioritize_current_resolution_backlog_v321(
        resolved_verification_csv=str(path), output_csv=priority_output_csv,
        summary_json=priority_summary_json, phase_label=phase_label)
    counts = out.drop_duplicates("queue_event_id")["resolution_status"].value_counts()
    return {"applied_rows": len(audit_rows),
            "verified_queue_events": int(counts.get("VERIFIED", 0)),
            "not_applicable_queue_events": int(counts.get("NOT_APPLICABLE", 0)),
            "unresolved_queue_events": int(counts.get("UNRESOLVED", 0)),
            "next_target": priority["next_target"], "next_target_rows": priority["next_target_rows"],
            "output_csv": str(path), "audit_csv": str(ap),
            "priority_output_csv": priority["output_csv"], "priority_summary_json": priority["summary_json"]}
