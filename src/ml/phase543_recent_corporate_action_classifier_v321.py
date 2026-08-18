from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _classify(description: str) -> tuple[str, str]:
    text = str(description or "").replace(" ", "")
    if "종속회사" in text or "자회사" in text or "특수관계인" in text:
        return "P3_REVIEW_NOT_APPLICABLE", "SUBSIDIARY_OR_RELATED_PARTY_ACTION"
    if any(value in text for value in ("청약결과", "발행결과", "증권발행실적", "합병등종료보고서", "매매거래정지")):
        return "P3_REVIEW_FOLLOWUP", "FOLLOWUP_OR_MARKET_ADMINISTRATION_NOTICE"
    if "주요사항보고서" in text and any(
        value in text for value in ("무상증자결정", "감자결정", "회사분할결정", "회사합병결정", "유상증자결정")
    ):
        return "P1_DIRECT_ISSUER_ACTION", "DIRECT_ISSUER_LEGAL_ACTION"
    if "유상증자신주발행가액" in text:
        return "P2_PARENT_ACTION_SUPPORTING_NOTICE", "PARENT_ACTION_SUPPORTING_NOTICE"
    return "P4_MANUAL_CLASSIFICATION", "UNCLASSIFIED_CORPORATE_ACTION"


def classify_recent_corporate_actions_v321(
    *, priority_queue_csv: str, output_csv: str, summary_json: str,
) -> dict:
    queue = pd.read_csv(priority_queue_csv, dtype=str).fillna("")
    required = {"queue_event_id", "code", "source_reference_date", "source_description", "resolution_priority"}
    missing = required - set(queue.columns)
    if missing:
        raise ValueError("priority queue missing columns: " + ", ".join(sorted(missing)))
    rows = queue[queue["resolution_priority"].eq("P2_RECENT_CORPORATE_ACTION")].copy()
    classified = rows["source_description"].map(_classify)
    rows["acquisition_priority"] = classified.map(lambda value: value[0])
    rows["classification_reason"] = classified.map(lambda value: value[1])
    rows["promotion_status"] = "REVIEW_ONLY_NOT_STRICT_EVIDENCE"
    rows = rows.sort_values(["acquisition_priority", "source_reference_date", "code"], ascending=[True, False, True])
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(target, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in rows["acquisition_priority"].value_counts().items()}
    summary = {
        "phase": "V3.2.1 Phase 5.43", "input_rows": len(rows),
        "priority_counts": counts,
        "direct_issuer_action_rows": int(rows["acquisition_priority"].eq("P1_DIRECT_ISSUER_ACTION").sum()),
        "next_target": "P1_DIRECT_ISSUER_ACTION", "auto_promoted_rows": 0, "fail_closed": True,
    }
    sp = Path(summary_json); sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"output_csv": str(target), "summary_json": str(sp)}
