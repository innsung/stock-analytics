from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd

from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321


TARGETS = {
    "7a01a66b177127696cb0": ("005380", "20241220000228", "20241219", "COMPLETION"),
    "5b4593551529a9bbb47f": ("005380", "20241024000243", "20241219", "DECISION"),
    "df20ee713b7b33e95580": ("005930", "20241031000508", "20250331", "DECISION"),
}


def _plain(parts: list[dict]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_overseas_listing_delistings_v321(
    dart_client, provider, *, actionable_queue_csv: str, disclosures_csv: str,
    documents_dir: str, evidence_output_csv: str, audit_output_csv: str,
    summary_json: str,
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    doc_root = Path(documents_dir); doc_root.mkdir(parents=True, exist_ok=True)
    evidence, audits, market_cache = [], [], {}
    for queue_id, (code, receipt, effective, stage) in TARGETS.items():
        q = queue[queue["queue_event_id"].eq(queue_id)]
        d = disclosures[disclosures["rcept_no"].eq(receipt)]
        status, reason, document_ok, breakpoints, error = "UNRESOLVED", "", False, -1, ""
        try:
            parts = dart_client.document_texts(receipt) if len(q) == 1 and len(d) == 1 else []
            for index, part in enumerate(parts):
                name = re.sub(r"[^0-9A-Za-z._-]", "_", str(part.get("name", "document.xml")))
                (doc_root / f"{receipt}_{index:02d}_{name}").write_text(str(part.get("text", "")), encoding="utf-8")
            text = _plain(parts)
            report = str(d.iloc[0]["report_nm"]) if len(d) == 1 else ""
            document_ok = bool(
                "해외증권시장" in report and "상장폐지" in report
                and "상장폐지" in text and ("DR" in text or "주식예탁증서" in text)
                and ("룩셈부르크" in text or "해외증권시장" in text)
            )
            if effective not in market_cache:
                market_cache[effective] = detect_adjustment_breakpoints_v321(
                    provider, code=code, center_date=effective, window_days=12)
            breakpoints = len(market_cache[effective])
            if len(q) != 1 or len(d) != 1:
                reason = "TARGET_OR_UNIQUE_OPENDART_DISCLOSURE_UNAVAILABLE"
            elif not document_ok:
                reason = "OVERSEAS_DR_DELISTING_DOCUMENT_TERMS_UNCONFIRMED"
            elif breakpoints:
                reason = "DOMESTIC_KRX_ADJUSTMENT_BREAKPOINT_REQUIRES_REVIEW"
            else:
                status = "NOT_APPLICABLE_EVIDENCE"
                reason = "OVERSEAS_DR_DELISTING_DOES_NOT_CHANGE_DOMESTIC_LISTED_SHAREHOLDER_UNITS"
                evidence.append({
                    "queue_event_id": queue_id,
                    "verification_source": "OPENDART_OVERSEAS_DR_DELISTING+KRX_DOMESTIC_NO_BREAKPOINT",
                    "verification_reference": f"DART:{receipt}", "resolution_note": reason,
                })
        except Exception as exc:  # audit external retrieval failures without promoting
            error = f"{type(exc).__name__}: {exc}"
            reason = "DOCUMENT_OR_MARKET_RETRIEVAL_FAILED"
        audits.append({"queue_event_id": queue_id, "code": code, "rcept_no": receipt,
                       "event_stage": stage, "overseas_delisting_date": effective,
                       "document_terms_confirmed": document_ok, "domestic_krx_breakpoints": breakpoints,
                       "verification_status": status, "resolution_note": reason, "error": error})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": len(TARGETS), "not_applicable_evidence_rows": len(evidence),
               "unresolved_rows": len(TARGETS) - len(evidence), "documents_dir": str(doc_root),
               "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
