from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


TARGETS = {
    "dab51aa4bea365f4cd4a": ("20200306", "20200306801032"),
    "5a95627db280d36dc327": ("20210630", "20210630800918"),
}
TITLE = "[기재정정]주요사항보고서(유상증자결정)(자회사의 주요경영사항)"


def audit_hdhyundai_subsidiary_rights_amendments_v321(*, actionable_queue_csv: str,
                                                       disclosures_csv: str,
                                                       evidence_output_csv: str,
                                                       audit_output_csv: str,
                                                       summary_json: str) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    evidence, audits = [], []
    for qid, (date, receipt) in TARGETS.items():
        q = queue[queue.queue_event_id.eq(qid)]
        d = disclosures[disclosures.rcept_no.eq(receipt)]
        queue_ok = (len(q) == 1 and q.iloc[0].code == "267250" and
                    q.iloc[0].source_reference_date == date and
                    q.iloc[0].source_description.strip() == TITLE)
        disclosure_ok = (len(d) == 1 and d.iloc[0].code == "267250" and
                         d.iloc[0].rcept_dt == date and d.iloc[0].report_nm.strip() == TITLE and
                         d.iloc[0].flr_nm.strip() == "HD현대")
        subsidiary_scope = "자회사의주요경영사항" in TITLE.replace(" ", "")
        ok = queue_ok and disclosure_ok and subsidiary_scope
        if not queue_ok:
            reason = "TARGET_QUEUE_IDENTITY_MISMATCH"
        elif not disclosure_ok:
            reason = "UNIQUE_OFFICIAL_DISCLOSURE_MISMATCH"
        elif not subsidiary_scope:
            reason = "SUBSIDIARY_SCOPE_UNCONFIRMED"
        else:
            reason = "SUBSIDIARY_RIGHTS_AMENDMENT_DOES_NOT_CHANGE_LISTED_PARENT_HOLDER_UNITS"
            evidence.append({"queue_event_id": qid,
                             "verification_source": "OPENDART_SUBSIDIARY_RIGHTS_AMENDMENT",
                             "verification_reference": f"DART:{receipt}",
                             "resolution_note": reason})
        audits.append({"queue_event_id": qid, "code": "267250", "rcept_dt": date,
                       "report_nm": TITLE, "rcept_no": receipt, "filer": "HD현대",
                       "queue_identity_valid": queue_ok, "official_disclosure_valid": disclosure_ok,
                       "subsidiary_scope_confirmed": subsidiary_scope,
                       "verification_status": "NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED",
                       "resolution_note": reason})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    ep.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(evidence, columns=["queue_event_id", "verification_source", "verification_reference", "resolution_note"]).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": len(TARGETS), "not_applicable_evidence_rows": len(evidence),
               "unresolved_rows": len(TARGETS) - len(evidence), "evidence_output_csv": str(ep),
               "audit_output_csv": str(ap), "fail_closed": True}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
