from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pandas as pd


def build_recent_dividend_evidence_inventory_v321(
    *, actionable_queue_csv: str, prior_coverage_audit_csv: str,
    strict_evidence_csvs: list[str], output_csv: str, summary_json: str,
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    targets = queue[queue["workstream"].eq("P3_RECENT_DIVIDEND_EVIDENCE")].copy()
    coverage = pd.read_csv(prior_coverage_audit_csv, dtype=str).fillna("")
    strict_frames = []
    for path in strict_evidence_csvs:
        p = Path(path)
        if p.exists():
            frame = pd.read_csv(p, dtype=str).fillna("")
            if {"code", "effective_date", "verification_reference"}.issubset(frame.columns):
                strict_frames.append(frame)
    strict = pd.concat(strict_frames, ignore_index=True) if strict_frames else pd.DataFrame(
        columns=["code", "effective_date", "verification_reference"])
    strict["code"] = strict["code"].astype(str).str.zfill(6)
    rows = []
    for target in targets.itertuples(index=False):
        ref = pd.to_datetime(target.source_reference_date, format="%Y%m%d")
        search_start = (ref - timedelta(days=450)).strftime("%Y%m%d")
        search_end = (ref + timedelta(days=30)).strftime("%Y%m%d")
        candidates = strict[strict["code"].eq(str(target.code).zfill(6))].copy()
        candidate_dates = sorted(set(candidates["effective_date"]))
        linkable = [d for d in candidate_dates if search_start <= d <= search_end]
        future = [d for d in candidate_dates if d > search_end]
        prior = coverage[coverage["queue_event_id"].eq(target.queue_event_id)]
        prior_status = prior.iloc[0]["coverage_status"] if len(prior) == 1 else "NO_PRIOR_COVERAGE_ROW"
        status = "LINKABLE_STRICT_EVIDENCE_REVIEW_REQUIRED" if linkable else "CORRECTED_HISTORICAL_MARKET_SEARCH_REQUIRED"
        rows.append({"queue_event_id": target.queue_event_id, "code": str(target.code).zfill(6),
            "source_reference_date": target.source_reference_date,
            "source_description": target.source_description,
            "prior_coverage_status": prior_status,
            "corrected_search_start": search_start, "corrected_search_end": search_end,
            "strict_candidate_dates": "|".join(candidate_dates),
            "linkable_strict_dates": "|".join(linkable),
            "future_non_linkable_dates": "|".join(future),
            "inventory_status": status,
            "promotion_status": "NOT_PROMOTED_REQUIRES_EVENT_DATE_LINKAGE"})
    output = pd.DataFrame(rows)
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(path, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in output["inventory_status"].value_counts().items()}
    summary = {"phase": "V3.2.1 Phase 5.67", "target_rows": len(output),
               "status_counts": counts,
               "future_non_linkable_rows": int(output["future_non_linkable_dates"].ne("").sum()),
               "auto_promoted_rows": 0, "next_target": "CORRECTED_HISTORICAL_MARKET_SEARCH",
               "fail_closed": True}
    sp = Path(summary_json); sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"output_csv": str(path), "summary_json": str(sp)}
