from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

TARGETS={"5ce0b0a11730d94dd579":("207940","20220420000396"),"94fc8c19b24f9848817f":("326030","20211124000177"),"e8a57cfcab5a370aeb74":("326030","20210331000006"),"06670d150820b10ff4c3":("326030","20210203000426")}
def _plain(parts):
 raw=" ".join(str(x.get("text","")) for x in parts);return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))
def _none_after(text,label):
 m=re.search(re.escape(label)+r".{0,80}해당사항 없음",text);return bool(m)
def audit_asset_transfer_completion_reports_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);evidence=[];audits=[]
 for qid,(code,receipt) in TARGETS.items():
  qt=q[q.queue_event_id.eq(qid)];dt=d[d.rcept_no.eq(receipt)];error="";terms=False
  try:
   parts=dart_client.document_texts(receipt) if len(qt)==len(dt)==1 else [];text=_plain(parts)
   for i,p in enumerate(parts):
    name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
   title=str(dt.iloc[0].report_nm) if len(dt)==1 else "";terms="합병등종료보고서(자산양수도)" in title.replace(" ","") and "합병등 종료보고서" in text and _none_after(text,"대주주등 지분변동 상황") and _none_after(text,"주식매수청구권 행사") and _none_after(text,"신주배정 등에 관한 사항")
  except Exception as exc:error=f"{type(exc).__name__}:{exc}"
  ok=len(qt)==len(dt)==1 and terms and not error
  if len(qt)!=1 or len(dt)!=1:reason="TARGET_OR_UNIQUE_DISCLOSURE_UNAVAILABLE"
  elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
  elif not terms:reason="ASSET_TRANSFER_NO_HOLDER_RIGHTS_TERMS_UNCONFIRMED"
  else:reason="CORPORATE_ASSET_TRANSFER_COMPLETION_HAS_NO_SHAREHOLDER_DISTRIBUTION"
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_ASSET_TRANSFER_COMPLETION_NO_HOLDER_RIGHTS","verification_reference":f"DART:{receipt}","resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":code,"rcept_no":receipt,"major_holder_change":"NONE","appraisal_rights":"NONE","new_share_allocation":"NONE","document_terms_confirmed":terms,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":error})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":4,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":4-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
