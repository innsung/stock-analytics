from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


TARGETS = {
    "0e0736f2cb914a175ff5": "20230601800619",
    "450cc52a858a88022e82": "20230623800597",
}


def _plain(parts: list[dict]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_samsung_heavy_preferred_delisting_warnings_v321(
    dart_client, *, actionable_queue_csv: str, disclosures_csv: str,
    documents_dir: str, evidence_output_csv: str, audit_output_csv: str,
    summary_json: str,
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    evidence, audits = [], []
    for queue_id, receipt in TARGETS.items():
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
            document_ok = ("삼성중공업" in report and "1우선주" in report
                           and "상장폐지 우려 예고" in report and "1우선주" in text
                           and "상장폐지" in text and "보통주" in text and "투자유의" in text)
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
        ok = len(q) == 1 and len(d) == 1 and document_ok and not error
        if len(q) != 1 or len(d) != 1: reason = "TARGET_OR_UNIQUE_KRX_DISCLOSURE_UNAVAILABLE"
        elif error: reason = "OPENDART_DOCUMENT_RETRIEVAL_FAILED"
        elif not document_ok: reason = "PREFERRED_SHARE_WARNING_TERMS_UNCONFIRMED"
        else: reason = "PREFERRED_SHARE_DELISTING_WARNING_IS_NOT_A_COMMON_SHARE_RETURN_EVENT"
        if ok:
            evidence.append({"queue_event_id": queue_id,
                "verification_source": "KRX_DISCLOSURE_PREFERRED_SECURITY_SCOPE",
                "verification_reference": f"DART:{receipt}", "resolution_note": reason})
        audits.append({"queue_event_id": queue_id, "code": "010140", "rcept_no": receipt,
            "affected_security": "SAMSUNG_HEAVY_INDUSTRIES_1_PREFERRED_SHARE",
            "modeled_security": "SAMSUNG_HEAVY_INDUSTRIES_COMMON_SHARE_010140",
            "document_terms_confirmed": document_ok,
            "verification_status": "NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED",
            "resolution_note": reason, "error": error})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    cols = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=cols).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": len(TARGETS), "not_applicable_evidence_rows": len(evidence),
        "unresolved_rows": len(TARGETS)-len(evidence), "documents_dir": str(root),
        "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
