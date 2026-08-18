from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

QUEUE_IDS={"ed8a338b14e8b8544525","b21c4168602acc050119"}
RECEIPTS={"20211222800770","20211222800771"}
SUBSIDIARIES={"SK hynix NAND Product Solutions Corp.","SK hynix Semiconductor (Dalian) Co., Ltd."}

def _plain(parts):
    raw=" ".join(str(x.get("text","")) for x in parts)
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))

def audit_skhynix_subsidiary_capital_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,
    documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
    q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("")
    qt=q[q.queue_event_id.isin(QUEUE_IDS)];dt=d[d.rcept_no.isin(RECEIPTS)];root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True)
    group_ok=len(qt)==2 and set(qt.queue_event_id)==QUEUE_IDS and len(dt)==2 and set(dt.rcept_no)==RECEIPTS;found=set();parent_rights=False;errors=[]
    for receipt in sorted(RECEIPTS):
        try:
            parts=dart_client.document_texts(receipt);text=_plain(parts)
            for i,p in enumerate(parts):
                name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
            title_rows=dt[dt.rcept_no.eq(receipt)];title=str(title_rows.iloc[0].report_nm) if len(title_rows)==1 else ""
            names={x for x in SUBSIDIARIES if x in text};found|=names
            group_ok=group_ok and "유상증자결정" in title and "종속회사의주요경영사항" in title.replace(" ","") and all(x in text for x in ("종속회사의 주요경영사항","종속회사인","신주의 종류와 수")) and len(names)==1
            parent_rights=parent_rights or "SK하이닉스 주주에게 신주" in text or "SK하이닉스 주주배정" in text
        except Exception as exc:errors.append(f"{receipt}:{type(exc).__name__}:{exc}");group_ok=False
    group_ok=group_ok and found==SUBSIDIARIES;ok=group_ok and not parent_rights and not errors
    if errors:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
    elif not group_ok:reason="SUBSIDIARY_CAPITAL_INCREASE_GROUP_MISMATCH"
    elif parent_rights:reason="PARENT_HOLDER_RIGHTS_LANGUAGE_REQUIRES_REVIEW"
    else:reason="SUBSIDIARY_CAPITAL_INCREASE_DOES_NOT_CHANGE_SKHYNIX_HOLDER_UNITS"
    ref="|".join(f"DART:{r}" for r in sorted(RECEIPTS));evidence=[];audits=[]
    for qid in sorted(QUEUE_IDS):
        if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_SKHYNIX_SUBSIDIARY_CAPITAL_DATE_GROUP","verification_reference":ref,"resolution_note":reason})
        audits.append({"queue_event_id":qid,"code":"000660","group_receipts":"|".join(sorted(RECEIPTS)),"subsidiaries":"|".join(sorted(found)),"document_group_valid":group_ok,"parent_holder_rights_language":parent_rights,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":"|".join(errors)})
    ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
    pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
    summary={"target_rows":2,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":2-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
