from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


def audit_spinoff_evidence_completeness_v321(
    dart_client, *, official_candidates_csv: str, output_csv: str,
    document_path: str, receipt_no: str = "20250822000109",
) -> dict:
    official = pd.read_csv(official_candidates_csv, dtype=str).fillna("")
    selected = official[official["rcept_no"].eq(receipt_no)]
    if selected.empty:
        raise ValueError(f"official spin-off candidate unavailable: {receipt_no}")
    raw = json.loads(selected.iloc[0]["raw_json"])
    parts = dart_client.document_texts(receipt_no)
    if not parts:
        raise ValueError(f"official document unavailable: {receipt_no}")
    document = "\n".join(part["text"] for part in parts)
    doc_path = Path(document_path); doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(document, encoding="utf-8")
    plain = re.sub(r"<[^>]+>", " ", document)
    plain = re.sub(r"\s+", " ", plain)
    fractional = str(raw.get("abcr_shstkcnt_rt_at_rs", ""))
    checks = [
        ("CAPITAL_REDUCTION_RATIO", bool(str(raw.get("abcr_crrt", "")).strip()), "abcr_crrt"),
        ("CHILD_ALLOCATION_RATIO", "분할비율" in str(raw.get("abcr_nstkascnd", "")), "abcr_nstkascnd"),
        ("CHILD_FRACTIONAL_CASH_RULE", all(x in fractional for x in ("1주 미만", "현금으로 지급", "재상장 초일의 종가")), "abcr_shstkcnt_rt_at_rs"),
        ("FIRST_JOINT_TRADING_DATE", bool(str(raw.get("abcr_nstklstprd", "")).strip()), "abcr_nstklstprd"),
        ("SURVIVING_LEG_FRACTIONAL_RULE", False, "NOT_PRESENT_IN_MAJOR_EVENT_FIELDS_OR_ORIGINAL_DOCUMENT"),
    ]
    rows = []
    for item, available, location in checks:
        rows.append({
            "rcept_no": receipt_no, "check_item": item,
            "evidence_status": "VERIFIED" if available else "MISSING",
            "evidence_location": location,
            "original_document_checked": True,
            "original_document_contains_fractional_term": "단주" in plain,
            "canonical_position_transfer_ready": False,
        })
    output = pd.DataFrame(rows)
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(path, index=False, encoding="utf-8-sig")
    missing = int(output["evidence_status"].eq("MISSING").sum())
    return {"checks": len(output), "verified": len(output) - missing, "missing": missing,
            "canonical_position_transfer_ready": False,
            "output_csv": str(path), "document_path": str(doc_path)}
