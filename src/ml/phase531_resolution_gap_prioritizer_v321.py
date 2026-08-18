from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def prioritize_resolution_gaps_v321(
    *, resolved_verification_csv: str, output_csv: str, summary_json: str
) -> dict:
    source = Path(resolved_verification_csv)
    if not source.exists():
        raise FileNotFoundError(str(source))
    frame = pd.read_csv(source, dtype=str).fillna("")
    required = {
        "queue_event_id", "code", "event_family", "source_reference_date",
        "source_description", "resolution_status",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("resolved verification missing columns: " + ", ".join(sorted(missing)))

    gaps = frame[frame["resolution_status"].eq("UNRESOLVED")].copy()
    gaps["code"] = gaps["code"].astype(str).str.zfill(6)
    gaps["reference_year"] = pd.to_numeric(
        gaps["source_reference_date"].str[:4], errors="coerce"
    ).fillna(0).astype(int)
    dividend = gaps["event_family"].eq("DIVIDEND_OR_DISTRIBUTION")
    recent = gaps["reference_year"].ge(2025)
    gaps["resolution_priority"] = "P4_HISTORICAL_CORPORATE_ACTION"
    gaps.loc[dividend & ~recent, "resolution_priority"] = "P3_HISTORICAL_DIVIDEND"
    gaps.loc[~dividend & recent, "resolution_priority"] = "P2_RECENT_CORPORATE_ACTION"
    gaps.loc[dividend & recent, "resolution_priority"] = "P1_RECENT_DIVIDEND"
    order = {
        "P1_RECENT_DIVIDEND": 1, "P2_RECENT_CORPORATE_ACTION": 2,
        "P3_HISTORICAL_DIVIDEND": 3, "P4_HISTORICAL_CORPORATE_ACTION": 4,
    }
    gaps["priority_order"] = gaps["resolution_priority"].map(order)
    gaps["code_unresolved_events"] = gaps.groupby("code")["queue_event_id"].transform("count")
    gaps = gaps.sort_values(
        ["priority_order", "reference_year", "code_unresolved_events", "code", "source_reference_date"],
        ascending=[True, False, False, True, False],
    )
    columns = [
        "queue_event_id", "code", "event_family", "source_reference_date",
        "reference_year", "source_description", "resolution_priority",
        "code_unresolved_events",
    ]
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    gaps[columns].to_csv(target, index=False, encoding="utf-8-sig")

    summary = {
        "phase": "V3.2.1 Phase 5.31",
        "input_rows": int(len(frame)),
        "unresolved_rows": int(len(gaps)),
        "priority_counts": {str(k): int(v) for k, v in gaps["resolution_priority"].value_counts().items()},
        "family_counts": {str(k): int(v) for k, v in gaps["event_family"].value_counts().items()},
        "top_codes": {str(k): int(v) for k, v in gaps["code"].value_counts().head(15).items()},
        "next_target": "P1_RECENT_DIVIDEND",
        "fail_closed": True,
    }
    summary_path = Path(summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"output_csv": str(target), "summary_json": str(summary_path)}
