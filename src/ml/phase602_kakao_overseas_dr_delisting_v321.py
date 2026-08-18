from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd

from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321


TARGETS = {
    "a47d0092b32486a3e1b4": ("20230511000691", "DECISION"),
    "f7a2e0aa51d2ade43600": ("20230525000446", "COMPLETION"),
}
EFFECTIVE_DATE = "20230525"


def _plain(parts: list[dict]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _date_present(text: str) -> bool:
    return bool(re.search(r"2023\D{0,20}05\D{0,20}25", text))


def audit_kakao_overseas_dr_delisting_v321(
    dart_client, provider, *, actionable_queue_csv: str, disclosures_csv: str,
    documents_dir: str, evidence_output_csv: str, audit_output_csv: str,
    summary_json: str,
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    evidence, audits = [], []
    try:
        breakpoints = detect_adjustment_breakpoints_v321(
            provider, code="035720", center_date=EFFECTIVE_DATE, window_days=12)
        market_error = ""
    except Exception as exc:
        breakpoints = pd.DataFrame(); market_error = f"{type(exc).__name__}:{exc}"
    for queue_id, (receipt, stage) in TARGETS.items():
        q = queue[queue["queue_event_id"].eq(queue_id)]
        d = disclosures[disclosures["rcept_no"].eq(receipt)]
        error = ""; document_ok = False
        try:
            parts = dart_client.document_texts(receipt) if len(q) == 1 and len(d) == 1 else []
            for index, part in enumerate(parts):
                name = re.sub(r"[^0-9A-Za-z._-]", "_", str(part.get("name", "document.xml")))
                (root / f"{receipt}_{index:02d}_{name}").write_text(str(part.get("text", "")), encoding="utf-8")
            text = _plain(parts)
            report = str(d.iloc[0]["report_nm"]) if len(d) == 1 else ""
            document_ok = ("해외증권시장" in report and "상장폐지" in report
                           and "상장폐지" in text and "GDR" in text
                           and "싱가포르" in text and _date_present(text))
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
        ok = len(q) == 1 and len(d) == 1 and document_ok and not market_error and breakpoints.empty
        if len(q) != 1 or len(d) != 1: reason = "TARGET_OR_UNIQUE_OPENDART_DISCLOSURE_UNAVAILABLE"
        elif error: reason = "OPENDART_DOCUMENT_RETRIEVAL_FAILED"
        elif not document_ok: reason = "KAKAO_SGX_GDR_DELISTING_TERMS_UNCONFIRMED"
        elif market_error: reason = "DOMESTIC_KRX_RETRIEVAL_FAILED"
        elif not breakpoints.empty: reason = "DOMESTIC_KRX_ADJUSTMENT_BREAKPOINT_REQUIRES_REVIEW"
        else: reason = "SGX_GDR_DELISTING_DOES_NOT_CHANGE_DOMESTIC_LISTED_SHAREHOLDER_UNITS"
        if ok:
            evidence.append({"queue_event_id": queue_id,
                "verification_source": "OPENDART_SGX_GDR_DELISTING+KRX_DOMESTIC_NO_BREAKPOINT",
                "verification_reference": f"DART:{receipt}|DART:20230511000691|DART:20230525000446",
                "resolution_note": reason})
        audits.append({"queue_event_id": queue_id, "code": "035720", "rcept_no": receipt,
            "event_stage": stage, "overseas_delisting_date": EFFECTIVE_DATE,
            "document_terms_confirmed": document_ok, "domestic_krx_breakpoints": len(breakpoints),
            "verification_status": "NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED",
            "resolution_note": reason, "error": error or market_error})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    cols = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=cols).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": len(TARGETS), "not_applicable_evidence_rows": len(evidence),
        "unresolved_rows": len(TARGETS)-len(evidence), "domestic_krx_breakpoints": len(breakpoints),
        "documents_dir": str(root), "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
