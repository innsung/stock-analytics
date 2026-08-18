from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


TARGETS = {
    "a8bc31e1ee484b708cf4": ("247540", "20220614", "유상증자최종발행가액확정", "20220614900162"),
    "bf3a71fead4ff3d7455f": ("247540", "20220620", "유상증자또는주식관련사채등의청약결과(자율공시)", "20220620900322"),
    "0d05d5530907c62a9429": ("247540", "20220624", "증권발행결과(자율공시)(주주배정 유상증자)", "20220624900396"),
    "e48c8b10197d27ba219c": ("207940", "20220329", "[기재정정]주요사항보고서(유상증자결정)", "20220329000875"),
    "6a055e79e96489b7a6dc": ("207940", "20220405", "[기재정정]주요사항보고서(유상증자결정)", "20220405000758"),
    "8d734540d8f782307c22": ("207940", "20220405", "유상증자신주발행가액(안내공시)", "20220405800264"),
    "8b3e78e855af61a991fc": ("207940", "20220411", "유상증자또는주식관련사채등의청약결과(자율공시)", "20220411800181"),
    "c661f3db63f03a378ac1": ("207940", "20220415", "유상증자또는주식관련사채등의발행결과(자율공시)", "20220415800641"),
}


def audit_rights_offering_followups_v321(*, actionable_queue_csv: str, disclosures_csv: str,
                                         evidence_output_csv: str, audit_output_csv: str,
                                         summary_json: str) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    evidence, audit = [], []
    for qid, (code, date, title, receipt) in TARGETS.items():
        q = queue[queue.queue_event_id.eq(qid)]
        d = disclosures[disclosures.rcept_no.eq(receipt)]
        queue_ok = (len(q) == 1 and q.iloc[0].code == code and
                    q.iloc[0].source_reference_date == date and
                    q.iloc[0].source_description.strip() == title)
        disclosure_ok = (len(d) == 1 and d.iloc[0].code == code and
                         d.iloc[0].rcept_dt == date and d.iloc[0].report_nm.strip() == title)
        is_market_action = "권리락" in title
        ok = queue_ok and disclosure_ok and not is_market_action
        if not queue_ok:
            reason = "TARGET_QUEUE_IDENTITY_MISMATCH"
        elif not disclosure_ok:
            reason = "UNIQUE_OFFICIAL_DISCLOSURE_MISMATCH"
        elif is_market_action:
            reason = "MARKET_ADJUSTMENT_NOTICE_REQUIRES_STRICT_EVENT_EVIDENCE"
        else:
            reason = "RIGHTS_OFFERING_FOLLOWUP_ADDS_NO_SEPARATE_HOLDER_RETURN_EVENT"
            evidence.append({
                "queue_event_id": qid,
                "verification_source": "OPENDART_RIGHTS_OFFERING_DISCLOSURE_CHAIN",
                "verification_reference": f"DART:{receipt}",
                "resolution_note": reason,
            })
        audit.append({"queue_event_id": qid, "code": code, "rcept_dt": date,
                      "report_nm": title, "rcept_no": receipt, "queue_identity_valid": queue_ok,
                      "official_disclosure_valid": disclosure_ok,
                      "separate_market_adjustment_notice": is_market_action,
                      "verification_status": "NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED",
                      "resolution_note": reason})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    ep.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(evidence, columns=["queue_event_id", "verification_source", "verification_reference", "resolution_note"]).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audit).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": len(TARGETS), "not_applicable_evidence_rows": len(evidence),
               "unresolved_rows": len(TARGETS) - len(evidence), "evidence_output_csv": str(ep),
               "audit_output_csv": str(ap), "fail_closed": True}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
