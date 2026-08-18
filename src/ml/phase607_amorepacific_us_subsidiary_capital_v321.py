from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

QUEUE_IDS={"0ba1a30b507e9d627377","0686e672d19dbfcf08f8"}
RECEIPTS={"20220901800248","20220901800284","20220901800466"}

def _plain(parts):
    raw=" ".join(str(x.get("text","")) for x in parts)
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))

def audit_amorepacific_us_subsidiary_capital_v321(dart_client,*,actionable_queue_csv:str,
    disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
    q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("")
    qt=q[q.queue_event_id.isin(QUEUE_IDS)];dt=d[d.rcept_no.isin(RECEIPTS)]
    root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);errors=[];documents=[]
    chain_ok=len(qt)==2 and set(qt.queue_event_id)==QUEUE_IDS and len(dt)==3 and set(dt.rcept_no)==RECEIPTS
    parent_rights=False
    for receipt in sorted(RECEIPTS):
        try:
            parts=dart_client.document_texts(receipt);text=_plain(parts)
            for i,p in enumerate(parts):
                name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")))
                (root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
            row=dt[dt.rcept_no.eq(receipt)];title=str(row.iloc[0].report_nm) if len(row)==1 else ""
            terms="유상증자결정" in title and "종속회사의주요경영사항" in title.replace(" ","") and all(x in text for x in ("종속회사의 주요경영사항","종속회사인 Amorepacific US Investment, Inc.","신주의 종류와 수","1,000,000"))
            chain_ok=chain_ok and terms;parent_rights=parent_rights or "아모레퍼시픽 주주에게 신주" in text or "아모레퍼시픽 주주배정" in text
            documents.append({"rcept_no":receipt,"terms_valid":terms})
        except Exception as exc:errors.append(f"{receipt}:{type(exc).__name__}:{exc}");chain_ok=False
    ok=chain_ok and not parent_rights and not errors
    if errors:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
    elif not chain_ok:reason="BASE_AND_CORRECTION_CHAIN_MISMATCH"
    elif parent_rights:reason="PARENT_HOLDER_RIGHTS_LANGUAGE_REQUIRES_REVIEW"
    else:reason="US_SUBSIDIARY_CAPITAL_INCREASE_DOES_NOT_CHANGE_AMOREPACIFIC_HOLDER_UNITS"
    ref="|".join(f"DART:{r}" for r in sorted(RECEIPTS));evidence=[];audits=[]
    for qid in sorted(QUEUE_IDS):
        if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_SUBSIDIARY_CAPITAL_BASE_CORRECTION_CHAIN","verification_reference":ref,"resolution_note":reason})
        audits.append({"queue_event_id":qid,"code":"090430","subsidiary":"Amorepacific US Investment, Inc.","chain_receipts":"|".join(sorted(RECEIPTS)),"subsidiary_new_shares":"1000000","document_chain_valid":chain_ok,"parent_holder_rights_language":parent_rights,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":"|".join(errors)})
    ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
    pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
    summary={"target_rows":2,"chain_documents":len(documents),"not_applicable_evidence_rows":len(evidence),"unresolved_rows":2-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)}
    sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
