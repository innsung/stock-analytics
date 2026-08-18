from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


EMPTY_VALUES = {"", "-", "0", "0.0"}


def resolve_explicit_no_dividend_v321(
    *, residual_csv: str, dividend_facts_csv: str, evidence_output_csv: str,
    audit_output_csv: str, business_year: str = "2024",
) -> dict:
    residual=pd.read_csv(residual_csv,dtype=str).fillna("")
    facts=pd.read_csv(dividend_facts_csv,dtype=str).fillna("")
    targets=residual[residual["residual_status"].eq("NO_DIRECT_DIVIDEND_DECISION")]
    evidence=[]; audits=[]
    for target in targets.itertuples(index=False):
        code=str(target.code).zfill(6)
        rows=facts[(facts["code"].astype(str).str.zfill(6).eq(code)) & facts["business_year"].eq(str(business_year))]
        per_share=rows[rows["se"].str.contains("주당 현금배당금",regex=False)]
        total=rows[rows["se"].str.contains("현금배당금총액",regex=False)]
        per_share_empty=not per_share.empty and per_share["thstrm"].map(lambda v:str(v).strip() in EMPTY_VALUES).all()
        total_empty=not total.empty and total["thstrm"].map(lambda v:str(v).strip() in EMPTY_VALUES).all()
        receipts=[]
        for raw in rows["raw_json"]:
            try:
                receipt=str(json.loads(raw).get("rcept_no", ""))
                if receipt: receipts.append(receipt)
            except (TypeError,ValueError,json.JSONDecodeError):
                continue
        receipts=sorted(set(receipts))
        valid=bool(per_share_empty and total_empty and receipts)
        status="EXPLICIT_ZERO_OR_DASH_CASH_DIVIDEND" if valid else "INSUFFICIENT_NO_DIVIDEND_EVIDENCE"
        reference="|".join(f"DART:{receipt}" for receipt in receipts)
        if valid:
            evidence.append({"queue_event_id":target.queue_event_id,
                "verification_source":"OPENDART_ALOT_MATTER_EXPLICIT_NO_CASH_DIVIDEND",
                "verification_reference":reference,
                "resolution_note":f"BUSINESS_YEAR_{business_year}_PER_SHARE_AND_TOTAL_CASH_DIVIDEND_EXPLICITLY_EMPTY"})
        audits.append({"queue_event_id":target.queue_event_id,"code":code,"business_year":business_year,
            "per_share_fact_rows":len(per_share),"total_fact_rows":len(total),
            "per_share_all_empty":per_share_empty,"total_all_empty":total_empty,
            "official_receipts":reference,"evidence_status":status,
            "promotion_status":"NOT_APPLICABLE_EVIDENCE" if valid else "NOT_PROMOTED"})
    ep,ap=Path(evidence_output_csv),Path(audit_output_csv); ep.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(evidence,columns=["queue_event_id","verification_source","verification_reference","resolution_note"]).to_csv(ep,index=False,encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
    return {"target_rows":len(targets),"not_applicable_evidence_rows":len(evidence),
            "unresolved_rows":len(targets)-len(evidence),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)}
