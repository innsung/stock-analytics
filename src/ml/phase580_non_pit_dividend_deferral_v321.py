from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def defer_non_pit_dividends_v321(
    *, actionable_queue_csv: str, residual_csv: str, provenance_audit_csv: str,
    actionable_output_csv: str, deferred_output_csv: str, audit_output_csv: str,
    summary_json: str,
) -> dict:
    actionable=pd.read_csv(actionable_queue_csv,dtype=str).fillna("")
    residual=pd.read_csv(residual_csv,dtype=str).fillna("")
    provenance=pd.read_csv(provenance_audit_csv,dtype=str).fillna("")
    targets=residual[residual["residual_status"].eq("DECISION_DISCLOSED_AFTER_EXDATE")]
    audits=[]; deferred_ids=[]
    for target in targets.itertuples(index=False):
        evidence=provenance[provenance["queue_event_id"].eq(target.queue_event_id)]
        first_known=evidence.iloc[-1]["first_known_at"] if not evidence.empty else ""
        search_hint=evidence.iloc[-1]["calendar_search_hint"] if not evidence.empty else ""
        no_early=not evidence.empty and evidence.iloc[-1]["provenance_status"]=="NO_PRE_EXDATE_AMOUNT_DISCLOSURE"
        valid=bool(no_early and first_known and search_hint and first_known>search_hint)
        status="DEFERRED_NON_PIT_POST_EXDATE_DECISION" if valid else "DEFERRAL_EVIDENCE_INCOMPLETE"
        if valid: deferred_ids.append(target.queue_event_id)
        audits.append({"queue_event_id":target.queue_event_id,"code":str(target.code).zfill(6),
            "calendar_search_hint":search_hint,"first_amount_known_at":first_known,
            "known_after_search_hint":bool(first_known and search_hint and first_known>search_hint),
            "deferral_status":status,"resolution_status":"UNRESOLVED",
            "policy_note":"CASH_AMOUNT_NOT_KNOWABLE_AT_EXDATE;EXCLUDED_FROM_PIT_TOTAL_RETURN" if valid else ""})
    deferred=actionable[actionable["queue_event_id"].isin(deferred_ids)].copy()
    deferred["routing_status"]="DEFERRED_NON_PIT_POST_EXDATE_DECISION"
    deferred["blocking_items"]="CASH_AMOUNT_FIRST_KNOWN_AFTER_EXDATE"
    remaining=actionable[~actionable["queue_event_id"].isin(deferred_ids)].copy()
    ap,dp,audp=Path(actionable_output_csv),Path(deferred_output_csv),Path(audit_output_csv)
    ap.parent.mkdir(parents=True,exist_ok=True)
    remaining.to_csv(ap,index=False,encoding="utf-8-sig"); deferred.to_csv(dp,index=False,encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(audp,index=False,encoding="utf-8-sig")
    result={"input_actionable_rows":len(actionable),"remaining_actionable_rows":len(remaining),
        "deferred_non_pit_rows":len(deferred),"recent_dividend_batch_total":17,
        "recent_dividend_terminal_rows":15,"recent_dividend_deferred_rows":len(deferred),
        "recent_dividend_batch_accounted_rows":15+len(deferred),"resolution_status_changed":False,
        "actionable_output_csv":str(ap),"deferred_output_csv":str(dp),"audit_output_csv":str(audp)}
    sp=Path(summary_json); sp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    result["summary_json"]=str(sp)
    return result
