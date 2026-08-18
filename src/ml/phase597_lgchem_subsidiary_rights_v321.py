from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


TARGETS = {
    "75097ecdc9093f806355": "20241205800081",
    "c2b653130a0126587aeb": "20241205800135",
}


def _plain(parts: list[dict]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_lgchem_subsidiary_rights_v321(
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
        status, reason, subsidiary, parent_holder_rights, error = "UNRESOLVED", "", "", False, ""
        try:
            parts = dart_client.document_texts(receipt) if len(q) == 1 and len(d) == 1 else []
            for index, part in enumerate(parts):
                name = re.sub(r"[^0-9A-Za-z._-]", "_", str(part.get("name", "document.xml")))
                (root / f"{receipt}_{index:02d}_{name}").write_text(str(part.get("text", "")), encoding="utf-8")
            text = _plain(parts)
            subsidiary = "LG Energy Solution Michigan, Inc." if "LG Energy Solution Michigan, Inc." in text else ""
            terms_ok = all(token in text for token in (
                "유상증자결정(종속회사의 주요경영사항)", "당사 종속회사", "출자결정", subsidiary))
            # A parent-holder rights event would explicitly assign new shares to LG Chem shareholders.
            parent_holder_rights = "LG화학 주주에게 신주" in text or "LG화학 주주배정" in text
            if len(q) != 1 or len(d) != 1:
                reason = "TARGET_OR_UNIQUE_OPENDART_DISCLOSURE_UNAVAILABLE"
            elif not terms_ok:
                reason = "SUBSIDIARY_CAPITAL_INCREASE_TERMS_UNCONFIRMED"
            elif parent_holder_rights:
                reason = "PARENT_HOLDER_RIGHTS_LANGUAGE_REQUIRES_REVIEW"
            else:
                status = "NOT_APPLICABLE_EVIDENCE"
                reason = "SUBSIDIARY_CAPITAL_INCREASE_DOES_NOT_CHANGE_LISTED_PARENT_SHAREHOLDER_UNITS"
                evidence.append({"queue_event_id": queue_id,
                    "verification_source": "OPENDART_SUBSIDIARY_CAPITAL_INCREASE_PRIMARY_DOCUMENT",
                    "verification_reference": f"DART:{receipt}", "resolution_note": reason})
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"; reason = "DOCUMENT_RETRIEVAL_FAILED"
        audits.append({"queue_event_id": queue_id, "code": "051910", "rcept_no": receipt,
                       "subsidiary_name": subsidiary, "parent_holder_rights_language": parent_holder_rights,
                       "verification_status": status, "resolution_note": reason, "error": error})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": len(TARGETS), "not_applicable_evidence_rows": len(evidence),
               "unresolved_rows": len(TARGETS)-len(evidence), "documents_dir": str(root),
               "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
