from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


TARGETS = {
    "097f38ed48920d234f40": ("20210527", "[기재정정]주요사항보고서(회사분할결정)", "20210527000395", "PHYSICAL_SPLIT"),
    "9cfee03860f626676f31": ("20210622", "[기재정정]회사분할합병결정(종속회사의주요경영사항)", "20210622800326", "SUBSIDIARY_SPLIT_MERGER"),
}


def audit_kakao_split_amendments_v321(*, actionable_queue_csv: str, disclosures_csv: str,
                                       phase590_audit_csv: str, phase616_audit_csv: str,
                                       evidence_output_csv: str, audit_output_csv: str,
                                       summary_json: str) -> dict:
    q = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    d = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    p590 = pd.read_csv(phase590_audit_csv, dtype=str).fillna("")
    p616 = pd.read_csv(phase616_audit_csv, dtype=str).fillna("")
    physical = p616[p616.queue_event_id.eq("2bd2a82cf3b7f796b9cd")]
    physical_ok = (len(physical) == 1 and physical.iloc[0].rcept_no == "20210701000279" and
                   physical.iloc[0].completion_type == "PHYSICAL_SPLIT" and
                   physical.iloc[0].newco_allocation == "100%_TO_PARENT" and
                   physical.iloc[0].listed_holder_new_shares == "NONE" and
                   physical.iloc[0].listed_holder_cash_consideration == "NONE" and
                   physical.iloc[0].verification_status == "NOT_APPLICABLE_EVIDENCE")
    subsidiary = p590[p590.queue_event_id.eq("5f56d4c50c16e2caf51c")]
    subsidiary_ok = (len(subsidiary) == 1 and subsidiary.iloc[0].controlling_rcept_no == "20210622800450" and
                     subsidiary.iloc[0].subsidiary_disclosure == "True" and
                     subsidiary.iloc[0].effective_date_candidate == "20210901" and
                     subsidiary.iloc[0].applicability_status == "EXPLICIT_SUBSIDIARY_RESTRUCTURING" and
                     subsidiary.iloc[0].promotion_status == "NOT_APPLICABLE_EVIDENCE")
    evidence, audits = [], []
    for qid, (date, title, receipt, kind) in TARGETS.items():
        qr, dr = q[q.queue_event_id.eq(qid)], d[d.rcept_no.eq(receipt)]
        identity_ok = (len(qr) == 1 and qr.iloc[0].code == "035720" and qr.iloc[0].source_reference_date == date and qr.iloc[0].source_description.strip() == title)
        disclosure_ok = (len(dr) == 1 and dr.iloc[0].code == "035720" and dr.iloc[0].rcept_dt == date and dr.iloc[0].report_nm.strip() == title and dr.iloc[0].flr_nm.strip() == "카카오")
        linked_ok = physical_ok if kind == "PHYSICAL_SPLIT" else subsidiary_ok
        ok = identity_ok and disclosure_ok and linked_ok
        if not identity_ok: reason = "TARGET_QUEUE_IDENTITY_MISMATCH"
        elif not disclosure_ok: reason = "UNIQUE_OFFICIAL_DISCLOSURE_MISMATCH"
        elif not linked_ok: reason = "LOCKED_SPLIT_AUDIT_LINKAGE_MISMATCH"
        elif kind == "PHYSICAL_SPLIT": reason = "PHYSICAL_SPLIT_AMENDMENT_ADDS_NO_LISTED_HOLDER_DISTRIBUTION"
        else: reason = "SUBSIDIARY_SPLIT_MERGER_AMENDMENT_HAS_NO_PARENT_SHARE_MECHANIC"
        if ok:
            core = "PHASE616:2bd2a82cf3b7f796b9cd" if kind == "PHYSICAL_SPLIT" else "PHASE590:5f56d4c50c16e2caf51c"
            evidence.append({"queue_event_id": qid, "verification_source": "OPENDART_KAKAO_SPLIT_CHAIN+LOCKED_CORE_AUDIT", "verification_reference": f"DART:{receipt}|{core}", "resolution_note": reason})
        audits.append({"queue_event_id": qid, "code": "035720", "rcept_no": receipt, "split_kind": kind,
                       "queue_identity_valid": identity_ok, "official_disclosure_valid": disclosure_ok,
                       "locked_core_audit_valid": linked_ok, "verification_status": "NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED", "resolution_note": reason})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    ep.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(evidence, columns=["queue_event_id", "verification_source", "verification_reference", "resolution_note"]).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": 2, "physical_split_core_valid": physical_ok, "subsidiary_split_core_valid": subsidiary_ok,
               "not_applicable_evidence_rows": len(evidence), "unresolved_rows": 2-len(evidence),
               "evidence_output_csv": str(ep), "audit_output_csv": str(ap), "fail_closed": True}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
