from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


QUEUE_ID = "be3607ed8285bb9a1295"
CORRECTION_RECEIPT = "20231026800280"
BASE_RECEIPT = "20231025800531"


def _plain(parts: list[dict]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_hd_ksoe_subsidiary_zero_ratio_merger_v321(
    dart_client, *, actionable_queue_csv: str, disclosures_csv: str,
    documents_dir: str, evidence_output_csv: str, audit_output_csv: str,
    summary_json: str,
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    target = queue[queue["queue_event_id"].eq(QUEUE_ID)]
    correction = disclosures[disclosures["rcept_no"].eq(CORRECTION_RECEIPT)]
    base = disclosures[disclosures["rcept_no"].eq(BASE_RECEIPT)]
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    error = ""; document_ok = False
    try:
        parts = dart_client.document_texts(BASE_RECEIPT) if len(target) == len(correction) == len(base) == 1 else []
        for index, part in enumerate(parts):
            name = re.sub(r"[^0-9A-Za-z._-]", "_", str(part.get("name", "document.xml")))
            (root / f"{BASE_RECEIPT}_{index:02d}_{name}").write_text(str(part.get("text", "")), encoding="utf-8")
        text = _plain(parts)
        correction_title = str(correction.iloc[0]["report_nm"]) if len(correction) == 1 else ""
        base_title = str(base.iloc[0]["report_nm"]) if len(base) == 1 else ""
        document_ok = ("자회사의 주요경영사항" in correction_title and "회사합병결정" in correction_title
            and "자회사의 주요경영사항" in base_title and "회사합병결정" in base_title
            and ("HD현대중공업" in text or "에이치디현대중공업" in text)
            and ("HD현대중공업모스" in text or "에이치디현대중공업모스" in text)
            and "지분 100%" in text and "1.0000000 : 0.0000000" in text
            and "발행할 신주는 없습니다" in text and "무증자 방식" in text)
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
    ok = len(target) == len(correction) == len(base) == 1 and document_ok and not error
    if len(target) != 1: reason = "UNIQUE_QUEUE_TARGET_UNAVAILABLE"
    elif len(correction) != 1 or len(base) != 1: reason = "UNIQUE_DISCLOSURE_CHAIN_UNAVAILABLE"
    elif error: reason = "OPENDART_BASE_DOCUMENT_RETRIEVAL_FAILED"
    elif not document_ok: reason = "SUBSIDIARY_ZERO_RATIO_MERGER_TERMS_UNCONFIRMED"
    else: reason = "SUBSIDIARY_ZERO_RATIO_NO_NEW_SHARE_MERGER_IS_NOT_A_PARENT_HOLDER_EVENT"
    evidence = []
    if ok:
        evidence.append({"queue_event_id": QUEUE_ID,
            "verification_source": "OPENDART_SUBSIDIARY_ZERO_RATIO_MERGER_CHAIN",
            "verification_reference": f"DART:{CORRECTION_RECEIPT}|DART:{BASE_RECEIPT}",
            "resolution_note": reason})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    cols = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=cols).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame([{"queue_event_id": QUEUE_ID, "code": "009540",
        "correction_rcept_no": CORRECTION_RECEIPT, "base_rcept_no": BASE_RECEIPT,
        "direct_legal_issuer": "HD_HYUNDAI_HEAVY_INDUSTRIES", "absorbed_company": "HD_HYUNDAI_HEAVY_INDUSTRIES_MOS",
        "ownership": "100%", "merger_ratio": "1.0000000:0.0000000", "new_shares": 0,
        "document_terms_confirmed": document_ok,
        "verification_status": "NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED",
        "resolution_note": reason, "error": error}]).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": 1, "not_applicable_evidence_rows": len(evidence),
        "unresolved_rows": 1-len(evidence), "documents_dir": str(root),
        "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
