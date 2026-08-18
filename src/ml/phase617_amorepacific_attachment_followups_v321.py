from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

TARGETS={
 "7d3737d4dc571175bbbc":("20210622000402","20210621000143","704428b155d277ae3a09","MERGER","0.1962185"),
 "0d72695fa80f997ed633":("20210624000091","20210623000067","2d54690554bd4b486389","SHARE_EXCHANGE","0.0046683"),
}
def audit_amorepacific_attachment_followups_v321(*,actionable_queue_csv:str,disclosures_csv:str,phase595_audit_csv:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");core=pd.read_csv(phase595_audit_csv,dtype=str).fillna("");evidence=[];audits=[]
 for qid,(attachment,base,core_qid,action,ratio) in TARGETS.items():
  qt=q[q.queue_event_id.eq(qid)];a=d[d.rcept_no.eq(attachment)];b=d[d.rcept_no.eq(base)];c=core[core.queue_event_id.eq(core_qid)]
  core_ok=len(c)==1 and str(c.iloc[0].controlling_rcept_no)==base and str(c.iloc[0].action_type)==action and str(c.iloc[0].event_date)=="20210901" and str(c.iloc[0].transaction_ratio)==ratio and str(c.iloc[0].event_window_breakpoints)=="0" and str(c.iloc[0].listing_window_breakpoints)=="0" and str(c.iloc[0].verification_status)=="NOT_APPLICABLE_EVIDENCE"
  titles_ok=len(a)==len(b)==1 and "[첨부정정]" in str(a.iloc[0].report_nm) and ("회사합병결정" in str(a.iloc[0].report_nm) if action=="MERGER" else "주식교환ㆍ이전결정" in str(a.iloc[0].report_nm)) and ("회사합병결정" in str(b.iloc[0].report_nm) if action=="MERGER" else "주식교환ㆍ이전결정" in str(b.iloc[0].report_nm))
  ok=len(qt)==1 and core_ok and titles_ok
  if len(qt)!=1:reason="UNIQUE_QUEUE_TARGET_UNAVAILABLE"
  elif not titles_ok:reason="ATTACHMENT_AND_BASE_DISCLOSURE_CHAIN_MISMATCH"
  elif not core_ok:reason="PHASE595_CORE_RESTRUCTURING_AUDIT_MISMATCH"
  else:reason="ATTACHMENT_CORRECTION_DUPLICATES_ALREADY_RESOLVED_RESTRUCTURING_EVENT"
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_ATTACHMENT_CHAIN+PHASE595_CORE_RESOLUTION","verification_reference":f"DART:{attachment}|DART:{base}|PHASE595:{core_qid}","resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":"090430","attachment_rcept_no":attachment,"base_rcept_no":base,"phase595_core_queue_event_id":core_qid,"action_type":action,"transaction_ratio":ratio,"disclosure_chain_valid":titles_ok,"phase595_core_valid":core_ok,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":2,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":2-len(evidence),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
