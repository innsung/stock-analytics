from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def audit_market_notice_coverage_v321(
    *, acquisition_manifest_csv: str, strict_evidence_csv: str,
    discovery_csvs: list[str], output_csv: str, summary_json: str,
) -> dict:
    acquisition = pd.read_csv(acquisition_manifest_csv, dtype=str).fillna("")
    strict = pd.read_csv(strict_evidence_csv, dtype=str).fillna("")
    required = {"queue_event_id", "code", "flr_nm", "acquisition_status"}
    missing = required - set(acquisition.columns)
    if missing:
        raise ValueError("acquisition manifest missing columns: " + ", ".join(sorted(missing)))
    strict_codes = set(strict["code"].astype(str).str.zfill(6)) if "code" in strict else set()
    discovered_codes: set[str] = set()
    sources_checked = []
    for value in discovery_csvs:
        path = Path(value)
        if not path.exists():
            raise FileNotFoundError(str(path))
        frame = pd.read_csv(path, dtype=str).fillna("")
        if "code" in frame:
            if "discovery_status" in frame:
                frame = frame[frame["discovery_status"].eq("DISCOVERED")]
            discovered_codes.update(frame["code"].astype(str).str.zfill(6))
        sources_checked.append(str(path))

    rows = []
    for _, item in acquisition.iterrows():
        code = str(item["code"]).zfill(6)
        if code in strict_codes:
            status = "STRICT_EVIDENCE_AVAILABLE"
        elif code in discovered_codes:
            status = "MARKET_NOTICE_DISCOVERED_NEEDS_DECISION_PAIRING"
        else:
            status = "NO_OFFICIAL_MARKET_NOTICE_FOUND_IN_SEARCH_SCOPE"
        rows.append({
            "queue_event_id": item["queue_event_id"], "code": code,
            "company_name": item["flr_nm"], "coverage_status": status,
            "search_start": "20260101", "search_end": "20260709",
            "searched_individual_notices": True, "searched_aggregate_notices": True,
            "searched_aggregate_attachments": True,
            "promotion_status": "NOT_PROMOTED_WITHOUT_OFFICIAL_NOTICE" if status.startswith("NO_") else "",
        })
    output = pd.DataFrame(rows)
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in output["coverage_status"].value_counts().items()}
    summary = {
        "phase": "V3.2.1 Phase 5.42", "target_rows": len(output),
        "coverage_counts": counts, "sources_checked": sources_checked,
        "search_start": "20260101", "search_end": "20260709", "fail_closed": True,
    }
    summary_path = Path(summary_json); summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"output_csv": str(target), "summary_json": str(summary_path)}
