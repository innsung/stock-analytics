from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def build_recent_dividend_acquisition_manifest_v321(
    *, priority_queue_csv: str, decision_disclosures_csv: str,
    strict_evidence_csv: str, output_csv: str, summary_json: str,
) -> dict:
    for value in (priority_queue_csv, decision_disclosures_csv, strict_evidence_csv):
        if not Path(value).exists():
            raise FileNotFoundError(value)
    queue = pd.read_csv(priority_queue_csv, dtype=str).fillna("")
    decisions = pd.read_csv(decision_disclosures_csv, dtype=str).fillna("")
    strict = pd.read_csv(strict_evidence_csv, dtype=str).fillna("")
    required_q = {"queue_event_id", "code", "resolution_priority", "source_reference_date"}
    required_d = {"code", "flr_nm", "known_at", "report_nm", "rcept_no"}
    if required_q - set(queue.columns):
        raise ValueError("priority queue missing columns: " + ", ".join(sorted(required_q - set(queue.columns))))
    if required_d - set(decisions.columns):
        raise ValueError("decision disclosures missing columns: " + ", ".join(sorted(required_d - set(decisions.columns))))

    targets = queue[queue["resolution_priority"].eq("P1_RECENT_DIVIDEND")].copy()
    targets["code"] = targets["code"].astype(str).str.zfill(6)
    decisions["code"] = decisions["code"].astype(str).str.zfill(6)
    recent = decisions[decisions["known_at"].ge("20250101")].sort_values(
        ["code", "known_at", "rcept_no"], ascending=[True, False, False]
    ).drop_duplicates("code")
    covered = set(strict["code"].astype(str).str.zfill(6)) if "code" in strict else set()
    out = targets.merge(
        recent[["code", "flr_nm", "known_at", "report_nm", "rcept_no"]],
        on="code", how="left",
    ).fillna("")
    out["acquisition_status"] = "NEEDS_COMPANY_DISCLOSURE_DISCOVERY"
    out.loc[out["flr_nm"].ne(""), "acquisition_status"] = "READY_FOR_KIND_MARKET_SEARCH"
    out.loc[out["code"].isin(covered), "acquisition_status"] = "STRICT_EVIDENCE_ALREADY_AVAILABLE"
    out["search_from"] = out["known_at"].where(out["known_at"].ne(""), "20250101")
    out["search_to"] = "20260709"
    columns = [
        "queue_event_id", "code", "source_reference_date", "flr_nm", "known_at",
        "report_nm", "rcept_no", "acquisition_status", "search_from", "search_to",
    ]
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    out[columns].to_csv(target, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in out["acquisition_status"].value_counts().items()}
    summary = {
        "phase": "V3.2.1 Phase 5.32", "target_rows": int(len(out)),
        "status_counts": counts, "strict_covered_codes": sorted(set(out.loc[
            out["acquisition_status"].eq("STRICT_EVIDENCE_ALREADY_AVAILABLE"), "code"
        ])), "fail_closed": True,
    }
    sp = Path(summary_json); sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"output_csv": str(target), "summary_json": str(sp)}
