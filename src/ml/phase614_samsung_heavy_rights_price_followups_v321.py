from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

TARGETS={"8074e01f6a8ee0a2c184":"20210914800549","4324b83c8aea3fb63d57":"20211025800529"}
CORE_QUEUE_ID="5432bce5e1925c59ed3b"
def _plain(parts):
 raw=" ".join(str(x.get("text","")) for x in parts);return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))
def audit_samsung_heavy_rights_price_followups_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,phase594_audit_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");core=pd.read_csv(phase594_audit_csv,dtype=str).fillna("");c=core[core.queue_event_id.eq(CORE_QUEUE_ID)]
 expected={"decision_rcept_no":"20211028000438","first_price_rcept_no":"20210914800549","record_date":"20210917","allotment_ratio":"0.331043387","first_issue_price":"5130.0","final_issue_price":"5130.0","effective_date":"20210916","verification_status":"STRICT_RIGHTS_EVIDENCE_READY"}
 core_ok=len(c)==1 and all(str(c.iloc[0].get(k,""))==v for k,v in expected.items()) and abs(float(c.iloc[0].adjustment_factor)-1.067524115755627)<1e-12
 root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);evidence=[];audits=[]
 for qid,receipt in TARGETS.items():
  qt=q[q.queue_event_id.eq(qid)];dt=d[d.rcept_no.eq(receipt)];error="";terms=False
  try:
   parts=dart_client.document_texts(receipt) if len(qt)==len(dt)==1 else [];text=_plain(parts)
   for i,p in enumerate(parts):
    name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
   title=str(dt.iloc[0].report_nm) if len(dt)==1 else "";terms="유상증자신주발행가액" in title.replace(" ","") and "신주발행가액" in text and "5,130" in text and ("확정 발행가액" in text or "1차 발행가액" in text)
  except Exception as exc:error=f"{type(exc).__name__}:{exc}"
  ok=len(qt)==len(dt)==1 and core_ok and terms and not error
  if len(qt)!=1 or len(dt)!=1:reason="TARGET_OR_UNIQUE_DISCLOSURE_UNAVAILABLE"
  elif not core_ok:reason="PHASE594_CORE_RIGHTS_AUDIT_MISMATCH"
  elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
  elif not terms:reason="RIGHTS_PRICE_NOTICE_TERMS_UNCONFIRMED"
  else:reason="PRICE_NOTICE_DUPLICATES_ALREADY_VERIFIED_RIGHTS_ADJUSTMENT_EVENT"
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_RIGHTS_PRICE_NOTICE+PHASE594_CORE_RESOLUTION","verification_reference":f"DART:{receipt}|PHASE594:{CORE_QUEUE_ID}","resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":"010140","rcept_no":receipt,"phase594_core_valid":core_ok,"final_issue_price":"5130","core_adjustment_factor":"1.067524115755627","document_terms_confirmed":terms,"underlying_rights_event_already_verified":True,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":error})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":2,"phase594_core_valid":core_ok,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":2-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
