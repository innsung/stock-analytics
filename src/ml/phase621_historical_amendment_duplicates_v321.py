from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

TARGETS={
 "9c9b83fcf9dc64c75fa2":("055550","20201123","[첨부정정]주요사항보고서(주식교환ㆍ이전결정)","20201123000205","6bc7eafe43bf25efd8f1","20201113001192","2a27e18980e3090f9275"),
 "f3202d7de6d8a1e2bf1c":("259960","20200928","[첨부정정]주요사항보고서(회사합병결정)","20200928000490","a5e86ec47cfa4e7613f2","20200925000100","a5e86ec47cfa4e7613f2"),
 "4437aa70603b1af124dd":("051900","20200210","[기재정정]주요사항보고서(회사합병결정)","20200210000395","fb9cff40447b84ab8245","20200129000363","fb9cff40447b84ab8245"),
}
def audit_historical_amendment_duplicates_v321(*,actionable_queue_csv:str,disclosures_csv:str,chain_csv:str,verification_csv:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");c=pd.read_csv(chain_csv,dtype=str).fillna("");v=pd.read_csv(verification_csv,dtype=str).fillna("");evidence=[];audits=[]
 for qid,(code,date,title,receipt,parent,parent_receipt,anchor) in TARGETS.items():
  qr=q[q.queue_event_id.eq(qid)];dr=d[d.rcept_no.eq(receipt)];cr=c[c.queue_event_id.eq(qid)];ar=v[v.queue_event_id.eq(anchor)]
  identity=len(qr)==1 and qr.iloc[0].code==code and qr.iloc[0].source_reference_date==date and qr.iloc[0].source_description.strip()==title
  disclosure=len(dr)==1 and dr.iloc[0].code==code and dr.iloc[0].rcept_dt==date and dr.iloc[0].report_nm.strip()==title
  chain=len(cr)==1 and cr.iloc[0].child_rcept_no==receipt and cr.iloc[0].candidate_parent_count=="1" and cr.iloc[0].candidate_parent_queue_event_ids==parent and cr.iloc[0].parent_candidate_status=="UNIQUE_PARENT_CANDIDATE"
  anchor_ok=len(ar)==1 and ar.iloc[0].resolution_status=="NOT_APPLICABLE"
  ok=identity and disclosure and chain and anchor_ok
  if not identity:reason="TARGET_QUEUE_IDENTITY_MISMATCH"
  elif not disclosure:reason="UNIQUE_OFFICIAL_DISCLOSURE_MISMATCH"
  elif not chain:reason="HISTORICAL_LEGAL_CHAIN_MISMATCH"
  elif not anchor_ok:reason="RESOLVED_CHAIN_ANCHOR_MISMATCH"
  else:reason="AMENDMENT_DUPLICATES_RESOLVED_OR_CONSOLIDATED_LEGAL_EVENT"
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_HISTORICAL_LEGAL_CHAIN+RESOLVED_ANCHOR","verification_reference":f"DART:{receipt}|DART:{parent_receipt}|ANCHOR:{anchor}","resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":code,"child_rcept_no":receipt,"parent_queue_event_id":parent,"parent_rcept_no":parent_receipt,"resolved_anchor_queue_event_id":anchor,"queue_identity_valid":identity,"official_disclosure_valid":disclosure,"unique_parent_chain_valid":chain,"resolved_anchor_valid":anchor_ok,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);ep.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(evidence,columns=["queue_event_id","verification_source","verification_reference","resolution_note"]).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":3,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":3-len(evidence),"evidence_output_csv":str(ep),"audit_output_csv":str(ap),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
