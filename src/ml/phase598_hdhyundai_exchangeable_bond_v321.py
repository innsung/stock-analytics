from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd

from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321


QUEUE_ID = "1567271747690326bc6b"
RESULT_RECEIPT = "20241111800423"
DECISION_RECEIPT = "20241011000438"


def _plain(parts: list[dict]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_hdhyundai_exchangeable_bond_v321(
    dart_client, provider, *, actionable_queue_csv: str, documents_dir: str,
    evidence_output_csv: str, audit_output_csv: str, summary_json: str,
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    target = queue[queue["queue_event_id"].eq(QUEUE_ID)]
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    texts, errors = {}, []
    for receipt in (DECISION_RECEIPT, RESULT_RECEIPT):
        try:
            parts = dart_client.document_texts(receipt)
            texts[receipt] = _plain(parts)
            for index, part in enumerate(parts):
                name = re.sub(r"[^0-9A-Za-z._-]", "_", str(part.get("name", "document.xml")))
                (root / f"{receipt}_{index:02d}_{name}").write_text(str(part.get("text", "")), encoding="utf-8")
        except Exception as exc:
            errors.append(f"{receipt}:{type(exc).__name__}:{exc}")
    decision, result = texts.get(DECISION_RECEIPT, ""), texts.get(RESULT_RECEIPT, "")
    terms_ok = all(token in decision for token in (
        "교환에 관한 사항", "사채발행방법 사모",
        "에이치디현대일렉트릭 주식회사", "717,125", "369,531"))
    result_ok = all(token in result for token in (
        "사모 교환사채", "실제발행주식수(주) -", "265,000,000,000", "2024-11-11"))
    breakpoints = detect_adjustment_breakpoints_v321(
        provider, code="267250", center_date="20241111", window_days=12)
    status, reason = "UNRESOLVED", ""
    evidence = []
    if len(target) != 1:
        reason = "UNIQUE_QUEUE_TARGET_UNAVAILABLE"
    elif errors:
        reason = "OPENDART_DOCUMENT_RETRIEVAL_FAILED"
    elif not terms_ok or not result_ok:
        reason = "EXCHANGEABLE_BOND_DECISION_OR_RESULT_TERMS_MISMATCH"
    elif not breakpoints.empty:
        reason = "KRX_PARENT_ADJUSTMENT_BREAKPOINT_REQUIRES_REVIEW"
    else:
        status = "NOT_APPLICABLE_EVIDENCE"
        reason = "SUBSIDIARY_SHARE_EXCHANGEABLE_BOND_DOES_NOT_CHANGE_ISSUER_HOLDER_UNITS"
        evidence.append({"queue_event_id": QUEUE_ID,
            "verification_source": "OPENDART_EXCHANGEABLE_BOND_DECISION_RESULT+KRX_NO_BREAKPOINT",
            "verification_reference": f"DART:{DECISION_RECEIPT}|DART:{RESULT_RECEIPT}",
            "resolution_note": reason})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame([{"queue_event_id": QUEUE_ID, "code": "267250",
        "decision_rcept_no": DECISION_RECEIPT, "result_rcept_no": RESULT_RECEIPT,
        "exchange_target": "HD Hyundai Electric common shares", "exchange_target_shares": 717125,
        "actual_issued_shares": 0, "actual_bond_amount": 265000000000,
        "payment_date": "20241111", "krx_adjustment_breakpoints": len(breakpoints),
        "verification_status": status, "resolution_note": reason, "errors": "|".join(errors)}]).to_csv(
            ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": 1, "not_applicable_evidence_rows": len(evidence),
        "unresolved_rows": 1-len(evidence), "documents_dir": str(root),
        "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
