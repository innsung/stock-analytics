from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def build_residual_dividend_backlog_v321(
    *, actionable_queue_csv: str, acquisition_csv: str, candidates_csv: str,
    discovery_audit_csv: str, output_csv: str, summary_json: str,
) -> dict:
    actionable = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    acquisition = pd.read_csv(acquisition_csv, dtype=str).fillna("")
    candidates = pd.read_csv(candidates_csv, dtype=str).fillna("")
    discovery = pd.read_csv(discovery_audit_csv, dtype=str).fillna("")
    targets = actionable[actionable["workstream"].eq("P3_RECENT_DIVIDEND_EVIDENCE")].copy()
    rows = []
    for item in targets.itertuples(index=False):
        qid = item.queue_event_id
        acq = acquisition[acquisition["queue_event_id"].eq(qid)]
        cand = candidates[candidates["queue_event_id"].eq(qid)]
        disc = discovery[discovery["queue_event_id"].eq(qid)]
        if acq.empty or not acq["acquisition_status"].eq("ACQUIRED").any():
            status = "NO_DIRECT_DIVIDEND_DECISION"
            next_action = "SEARCH_ALTERNATIVE_OFFICIAL_DECISION_SOURCE"
        elif not cand.empty and cand["candidate_status"].eq("LATE_DISCLOSURE_NOT_PIT_ELIGIBLE").all():
            status = "DECISION_DISCLOSED_AFTER_EXDATE"
            next_action = "SEARCH_PRE_EXDATE_ANNOUNCEMENT_EVIDENCE"
        elif not disc.empty and disc["status"].eq("AMBIGUOUS_OFFICIAL_NOTICES").any():
            status = "AMBIGUOUS_KIND_MARKET_NOTICE"
            next_action = "DISAMBIGUATE_KIND_NOTICE_BY_SECURITY_MEMBERSHIP_AND_DATE"
        elif not disc.empty and disc["status"].eq("NO_MATCHING_OFFICIAL_NOTICE").any():
            status = "NO_MATCHING_KIND_MARKET_NOTICE"
            next_action = "BROADEN_KIND_MARKET_NOTICE_SEARCH"
        else:
            status = "EVIDENCE_GAP_UNCLASSIFIED"
            next_action = "MANUAL_OFFICIAL_EVIDENCE_REVIEW"
        rows.append({
            "queue_event_id": qid, "code": str(item.code).zfill(6),
            "source_reference_date": item.source_reference_date,
            "source_description": item.source_description,
            "residual_status": status, "next_action": next_action,
            "resolution_status": "UNRESOLVED", "promotion_status": "NOT_PROMOTED_REQUIRES_STRICT_EVIDENCE",
        })
    output = pd.DataFrame(rows)
    order = {"AMBIGUOUS_KIND_MARKET_NOTICE": 1, "NO_MATCHING_KIND_MARKET_NOTICE": 2,
             "DECISION_DISCLOSED_AFTER_EXDATE": 3, "NO_DIRECT_DIVIDEND_DECISION": 4,
             "EVIDENCE_GAP_UNCLASSIFIED": 5}
    if not output.empty:
        output["resolution_order"] = output["residual_status"].map(order).fillna(99).astype(int)
        output = output.sort_values(["resolution_order", "source_reference_date", "code"], ascending=[True, False, True])
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in output["residual_status"].value_counts().to_dict().items()}
    result = {"target_rows": len(output), "status_counts": counts,
              "next_target": output.iloc[0]["residual_status"] if not output.empty else "NONE",
              "next_target_rows": int(output["residual_status"].eq(output.iloc[0]["residual_status"]).sum()) if not output.empty else 0,
              "output_csv": str(target), "resolution_status_changed": False}
    summary = Path(summary_json); summary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["summary_json"] = str(summary)
    return result
