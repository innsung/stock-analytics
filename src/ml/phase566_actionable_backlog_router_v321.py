from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def route_actionable_resolution_backlog_v321(
    *, priority_queue_csv: str, direct_action_audit_csv: str,
    complex_evidence_audit_csv: str, actionable_output_csv: str,
    blocked_output_csv: str, summary_json: str,
) -> dict:
    queue = pd.read_csv(priority_queue_csv, dtype=str).fillna("")
    direct = pd.read_csv(direct_action_audit_csv, dtype=str).fillna("")
    complex_audit = pd.read_csv(complex_evidence_audit_csv, dtype=str).fillna("")
    required_q = {"queue_event_id", "workstream", "priority_order"}
    if required_q - set(queue.columns):
        raise ValueError("priority queue missing routing columns")
    if {"queue_event_id", "row_status"} - set(direct.columns):
        raise ValueError("direct action audit missing routing columns")
    if {"check_item", "evidence_status"} - set(complex_audit.columns):
        raise ValueError("complex evidence audit missing routing columns")
    missing_complex = complex_audit[~complex_audit["evidence_status"].eq("VERIFIED")]
    core_ids = set(direct.loc[direct["row_status"].eq("CORE_EVENT_UNRESOLVED"), "queue_event_id"])
    blocked_ids = core_ids if not missing_complex.empty else set()
    blocked = queue[queue["queue_event_id"].isin(blocked_ids)].copy()
    blocked["routing_status"] = "BLOCKED_PENDING_EXTERNAL_COMPLEX_ACTION_EVIDENCE"
    blocked["blocking_items"] = "|".join(missing_complex["check_item"].tolist())
    actionable = queue[~queue["queue_event_id"].isin(blocked_ids)].copy()
    actionable["routing_status"] = "ACTIONABLE"
    actionable = actionable.sort_values(["priority_order", "source_reference_date", "code"],
                                        ascending=[True, False, True])
    ap, bp = Path(actionable_output_csv), Path(blocked_output_csv)
    ap.parent.mkdir(parents=True, exist_ok=True); bp.parent.mkdir(parents=True, exist_ok=True)
    actionable.to_csv(ap, index=False, encoding="utf-8-sig")
    blocked.to_csv(bp, index=False, encoding="utf-8-sig")
    next_target = actionable.iloc[0]["workstream"] if not actionable.empty else "NONE"
    next_rows = int(actionable["workstream"].eq(next_target).sum()) if next_target != "NONE" else 0
    summary = {"phase": "V3.2.1 Phase 5.66", "input_unresolved_rows": len(queue),
               "actionable_rows": len(actionable), "blocked_rows": len(blocked),
               "blocked_queue_event_ids": blocked["queue_event_id"].tolist(),
               "next_actionable_target": next_target, "next_actionable_rows": next_rows,
               "resolution_status_changed": False, "fail_closed": True}
    sp = Path(summary_json); sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"actionable_output_csv": str(ap), "blocked_output_csv": str(bp),
                      "summary_json": str(sp)}
