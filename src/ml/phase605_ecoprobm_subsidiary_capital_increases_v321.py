from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


GROUPS = {
    "20220927": ({"c967600495470be16190", "3e19de4af1cf3cc303ec"}, {"20220927900593", "20220927900596"}),
    "20221028": ({"16e2f6674621246c079f"}, {"20221028900699"}),
    "20221117": ({"22d5a4aaf8af8a58c65e", "1eab101f5f4c6cd1f855"}, {"20221117900445", "20221117900464"}),
    "20230330": ({"06363c425de0bd51efe6", "a16deca08a43c1b5479e"}, {"20230330902503", "20230330902510"}),
}


def _plain(parts: list[dict]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_ecoprobm_subsidiary_capital_increases_v321(
    dart_client, *, actionable_queue_csv: str, disclosures_csv: str,
    documents_dir: str, evidence_output_csv: str, audit_output_csv: str,
    summary_json: str,
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    evidence, audits = [], []
    for date, (queue_ids, receipts) in GROUPS.items():
        q = queue[queue["queue_event_id"].isin(queue_ids)]
        d = disclosures[disclosures["rcept_no"].isin(receipts)]
        docs_ok = True; parent_rights = False; errors = []
        if len(q) != len(queue_ids) or set(q["queue_event_id"]) != queue_ids:
            docs_ok = False
        if len(d) != len(receipts) or set(d["rcept_no"]) != receipts:
            docs_ok = False
        for receipt in sorted(receipts):
            try:
                parts = dart_client.document_texts(receipt)
                for index, part in enumerate(parts):
                    name = re.sub(r"[^0-9A-Za-z._-]", "_", str(part.get("name", "document.xml")))
                    (root/f"{receipt}_{index:02d}_{name}").write_text(str(part.get("text", "")), encoding="utf-8")
                text = _plain(parts)
                title_rows = d[d["rcept_no"].eq(receipt)]
                title = str(title_rows.iloc[0]["report_nm"]) if len(title_rows) == 1 else ""
                terms = ("유상증자결정" in title and "종속회사의주요경영사항" in title.replace(" ", "")
                         and "유상증자결정" in text and "종속회사의 주요경영사항" in text
                         and "종속회사인" in text and "신주의 종류와 수" in text)
                parent_rights = parent_rights or "에코프로비엠 주주에게 신주" in text or "에코프로비엠 주주배정" in text
                docs_ok = docs_ok and terms
            except Exception as exc:
                errors.append(f"{receipt}:{type(exc).__name__}:{exc}"); docs_ok = False
        ok = docs_ok and not parent_rights and not errors
        if errors: reason = "OPENDART_DOCUMENT_RETRIEVAL_FAILED"
        elif not docs_ok: reason = "SUBSIDIARY_CAPITAL_INCREASE_GROUP_MISMATCH"
        elif parent_rights: reason = "PARENT_HOLDER_RIGHTS_LANGUAGE_REQUIRES_REVIEW"
        else: reason = "SUBSIDIARY_CAPITAL_INCREASE_DOES_NOT_CHANGE_LISTED_PARENT_HOLDER_UNITS"
        reference = "|".join(f"DART:{receipt}" for receipt in sorted(receipts))
        for queue_id in sorted(queue_ids):
            if ok:
                evidence.append({"queue_event_id": queue_id,
                    "verification_source": "OPENDART_SUBSIDIARY_CAPITAL_INCREASE_DATE_GROUP",
                    "verification_reference": reference, "resolution_note": reason})
            audits.append({"queue_event_id": queue_id, "code": "247540", "disclosure_date": date,
                "group_receipts": "|".join(sorted(receipts)), "document_group_valid": docs_ok,
                "parent_holder_rights_language": parent_rights,
                "verification_status": "NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED",
                "resolution_note": reason, "error": "|".join(errors)})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    cols = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=cols).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    target_count = sum(len(ids) for ids, _ in GROUPS.values())
    summary = {"target_rows": target_count, "date_groups": len(GROUPS),
        "not_applicable_evidence_rows": len(evidence), "unresolved_rows": target_count-len(evidence),
        "documents_dir": str(root), "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
