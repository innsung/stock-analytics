from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _workstream(row: pd.Series) -> tuple[str, str]:
    family = row["event_family"]
    date = str(row["source_reference_date"])
    text = str(row["source_description"]).replace(" ", "")
    recent = date >= "20250101"
    subsidiary = any(token in text for token in ("종속회사", "자회사", "특수관계인"))
    followup = any(token in text for token in ("발행결과", "청약결과", "종료보고서", "매매거래정지"))
    if family == "CORPORATE_ACTION" and recent and subsidiary:
        return "P1_SUBSIDIARY_APPLICABILITY_REVIEW", "HIGH_VOLUME_POTENTIAL_NOT_APPLICABLE_CLUSTER"
    if family == "CORPORATE_ACTION" and recent and not followup:
        return "P2_RECENT_DIRECT_ACTION_REVIEW", "DIRECT_OR_UNCLASSIFIED_RECENT_ACTION"
    if family == "DIVIDEND_OR_DISTRIBUTION" and recent:
        return "P3_RECENT_DIVIDEND_EVIDENCE", "RECENT_DIVIDEND_REQUIRES_UNIQUE_MARKET_EVIDENCE"
    if family == "CORPORATE_ACTION" and recent:
        return "P4_RECENT_FOLLOWUP_REVIEW", "FOLLOWUP_NOTICE_REQUIRES_EVENT_LINKAGE"
    return "P5_HISTORICAL_BACKLOG", "LOWER_RECENCY_BACKLOG"


def prioritize_current_resolution_backlog_v321(
    *, resolved_verification_csv: str, output_csv: str, summary_json: str,
    phase_label: str = "V3.2.1 Phase 5.55",
) -> dict:
    frame = pd.read_csv(resolved_verification_csv, dtype=str).fillna("")
    required = {"queue_event_id", "code", "event_family", "source_reference_date",
                "source_description", "resolution_status", "resolution_note"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("verification backlog missing columns: " + ", ".join(sorted(missing)))
    rows = frame[frame["resolution_status"].eq("UNRESOLVED")].copy()
    classified = rows.apply(_workstream, axis=1)
    rows["workstream"] = classified.map(lambda x: x[0])
    rows["priority_reason"] = classified.map(lambda x: x[1])
    order = {name: i for i, name in enumerate([
        "P1_SUBSIDIARY_APPLICABILITY_REVIEW", "P2_RECENT_DIRECT_ACTION_REVIEW",
        "P3_RECENT_DIVIDEND_EVIDENCE", "P4_RECENT_FOLLOWUP_REVIEW",
        "P5_HISTORICAL_BACKLOG"], 1)}
    rows["priority_order"] = rows["workstream"].map(order)
    rows["auto_promotion_status"] = "NOT_PROMOTED_REQUIRES_EVIDENCE"
    rows = rows.sort_values(["priority_order", "source_reference_date", "code"],
                            ascending=[True, False, True])
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in rows["workstream"].value_counts().items()}
    next_target = next((name for name in order if counts.get(name, 0) > 0), "NONE")
    summary = {"phase": phase_label, "input_rows": len(frame),
               "unresolved_rows": len(rows), "workstream_counts": counts,
               "next_target": next_target,
               "next_target_rows": counts.get(next_target, 0),
               "auto_promoted_rows": 0, "fail_closed": True}
    sp = Path(summary_json); sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"output_csv": str(path), "summary_json": str(sp)}
