from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

TARGETS={
 "2bd2a82cf3b7f796b9cd":("035720","20210701000279","PHYSICAL_SPLIT"),
 "c29d7a194fad3495c178":("051910","20201204000451","PHYSICAL_SPLIT"),
 "4d12971f83674fe5bdbd":("267250","20200701000308","PHYSICAL_SPLIT"),
 "ddf174d8dbc151772cf4":("267250","20200504000001","PHYSICAL_SPLIT"),
 "7cf0d77b6cf406f0d617":("068270","20201201000003","BUSINESS_TRANSFER"),
}
def _plain(parts):
 raw=" ".join(str(x.get("text","")) for x in parts);return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))
def audit_physical_split_business_transfer_completions_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);evidence=[];audits=[]
 for qid,(code,receipt,kind) in TARGETS.items():
  qt=q[q.queue_event_id.eq(qid)];dt=d[d.rcept_no.eq(receipt)];error="";terms=False
  try:
   parts=dart_client.document_texts(receipt) if len(qt)==len(dt)==1 else [];text=_plain(parts)
   for i,p in enumerate(parts):
    name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
   title=str(dt.iloc[0].report_nm) if len(dt)==1 else "";common="합병등종료보고서" in title.replace(" ","") and "합병등 종료보고서" in text and "대주주등 지분변동 상황" in text and "신주배정 등에 관한 사항" in text
   if kind=="PHYSICAL_SPLIT":terms=common and ("물적분할" in text or "물적 분할" in text) and "100% 배정" in text and ("변동은 없습니다" in text or "해당사항 없습니다" in text or "해당사항이 없습니다" in text)
   else:terms=common and "영업양수" in text and "발행할 신주" in text and ("지급할 교부금은 없습니다" in text or "지급한 교부금은 없습니다" in text) and "해당사항 없음" in text
  except Exception as exc:error=f"{type(exc).__name__}:{exc}"
  ok=len(qt)==len(dt)==1 and terms and not error
  if len(qt)!=1 or len(dt)!=1:reason="TARGET_OR_UNIQUE_DISCLOSURE_UNAVAILABLE"
  elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
  elif not terms:reason="NO_LISTED_HOLDER_DISTRIBUTION_TERMS_UNCONFIRMED"
  elif kind=="PHYSICAL_SPLIT":reason="PHYSICAL_SPLIT_ALLOCATES_NEWCO_TO_PARENT_NOT_LISTED_HOLDERS"
  else:reason="BUSINESS_TRANSFER_COMPLETION_HAS_NO_NEW_SHARES_OR_CONSIDERATION_TO_HOLDERS"
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_COMPLETION_NO_LISTED_HOLDER_DISTRIBUTION","verification_reference":f"DART:{receipt}","resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":code,"rcept_no":receipt,"completion_type":kind,"newco_allocation":"100%_TO_PARENT" if kind=="PHYSICAL_SPLIT" else "NONE","listed_holder_new_shares":"NONE","listed_holder_cash_consideration":"NONE","document_terms_confirmed":terms,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":error})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":5,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":5-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
