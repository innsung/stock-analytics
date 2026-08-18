from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

TARGETS={
 "6f31d412304c9f949a0d":("20210707","수시공시의무관련사항(공정공시)(유상증자 계획)","20210707900416","PRELIMINARY_PLAN_HAS_NO_EFFECTIVE_HOLDER_EVENT"),
 "1c64eb68f6a3d9f56069":("20220614","[기재정정]주요사항보고서(유무상증자결정)","20220614000068","DECISION_DISCLOSURE_IS_SUPPORTING_DOCUMENT_FOR_SEPARATE_MARKET_ADJUSTMENT"),
}
EXECUTION_QIDS={"a8bc31e1ee484b708cf4","bf3a71fead4ff3d7455f","0d05d5530907c62a9429"}
MARKET_QID="fe87e76e0b26e616df1c"
def audit_ecoprobm_rights_support_disclosures_v321(*,actionable_queue_csv:str,disclosures_csv:str,phase618_audit_csv:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");p=pd.read_csv(phase618_audit_csv,dtype=str).fillna("")
 executed=p[p.queue_event_id.isin(EXECUTION_QIDS)];execution_ok=len(executed)==3 and set(executed.queue_event_id)==EXECUTION_QIDS and executed.verification_status.eq("NOT_APPLICABLE_EVIDENCE").all() and executed.official_disclosure_valid.eq("True").all()
 market=q[q.queue_event_id.eq(MARKET_QID)];market_preserved=len(market)==1 and market.iloc[0].source_description.strip()=="권리락(무상증자)" and market.iloc[0].resolution_status=="UNRESOLVED"
 evidence=[];audits=[]
 for qid,(date,title,receipt,note) in TARGETS.items():
  qr=q[q.queue_event_id.eq(qid)];dr=d[d.rcept_no.eq(receipt)];identity=len(qr)==1 and qr.iloc[0].code=="247540" and qr.iloc[0].source_reference_date==date and qr.iloc[0].source_description.strip()==title;disclosure=len(dr)==1 and dr.iloc[0].code=="247540" and dr.iloc[0].rcept_dt==date and dr.iloc[0].report_nm.strip()==title and dr.iloc[0].flr_nm.strip()=="에코프로비엠";ok=identity and disclosure and execution_ok and market_preserved
  if not identity:reason="TARGET_QUEUE_IDENTITY_MISMATCH"
  elif not disclosure:reason="UNIQUE_OFFICIAL_DISCLOSURE_MISMATCH"
  elif not execution_ok:reason="PHASE618_EXECUTION_CHAIN_MISMATCH"
  elif not market_preserved:reason="SEPARATE_MARKET_ADJUSTMENT_QUEUE_NOT_PRESERVED"
  else:reason=note
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_ECOPROBM_RIGHTS_CHAIN+PHASE618_EXECUTION_AUDIT","verification_reference":f"DART:{receipt}|PHASE618_EXECUTION_CHAIN|MARKET_QUEUE:{MARKET_QID}","resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":"247540","rcept_no":receipt,"queue_identity_valid":identity,"official_disclosure_valid":disclosure,"phase618_execution_chain_valid":execution_ok,"separate_market_adjustment_preserved":market_preserved,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);ep.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(evidence,columns=["queue_event_id","verification_source","verification_reference","resolution_note"]).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":2,"execution_chain_valid":bool(execution_ok),"market_adjustment_preserved":bool(market_preserved),"not_applicable_evidence_rows":len(evidence),"unresolved_rows":2-len(evidence),"evidence_output_csv":str(ep),"audit_output_csv":str(ap),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
