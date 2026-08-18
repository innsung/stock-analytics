from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

EXPECTED={"VERIFIED":25,"NOT_APPLICABLE":371,"UNRESOLVED":3}
def build_release_quality_gate_v321(*,verification_csv:str,actionable_csv:str,deferred_csv:str,blocked_csv:str,audit_output_csv:str,summary_json:str)->dict:
 v=pd.read_csv(verification_csv,dtype=str).fillna("");a=pd.read_csv(actionable_csv,dtype=str).fillna("");d=pd.read_csv(deferred_csv,dtype=str).fillna("");b=pd.read_csv(blocked_csv,dtype=str).fillna("")
 counts=v.resolution_status.value_counts().to_dict();verified=v[v.resolution_status.eq("VERIFIED")];na=v[v.resolution_status.eq("NOT_APPLICABLE")];unresolved=v[v.resolution_status.eq("UNRESOLVED")]
 required_verified=["effective_date","known_at","action_type","adjustment_factor","verification_source","verification_reference","resolution_note"]
 checks=[
  ("TOTAL_ROWS_399",len(v)==399,f"actual={len(v)}"),
  ("UNIQUE_QUEUE_EVENT_IDS",v.queue_event_id.nunique()==len(v),f"unique={v.queue_event_id.nunique()}"),
  ("EXPECTED_STATUS_COUNTS",all(counts.get(k,0)==n for k,n in EXPECTED.items()),json.dumps(counts,ensure_ascii=False,sort_keys=True)),
  ("VALID_SIX_DIGIT_CODES",v.code.str.fullmatch(r"\d{6}").all(),"all codes must be six digits"),
  ("VERIFIED_FIELDS_COMPLETE",verified[required_verified].ne("").all(axis=None),f"rows={len(verified)}"),
  ("VERIFIED_DATE_ORDER_VALID",(verified.known_at<=verified.effective_date).all(),"known_at <= effective_date"),
  ("VERIFIED_FACTORS_POSITIVE",pd.to_numeric(verified.adjustment_factor,errors="coerce").gt(0).all(),"all factors > 0"),
  ("NOT_APPLICABLE_EVIDENCE_COMPLETE",na[["verification_source","verification_reference","resolution_note"]].ne("").all(axis=None),f"rows={len(na)}"),
  ("ACTIONABLE_QUEUE_EMPTY",len(a)==0,f"rows={len(a)}"),
  ("DEFERRED_QUEUE_TWO",len(d)==2,f"rows={len(d)}"),
  ("BLOCKED_QUEUE_ONE",len(b)==1,f"rows={len(b)}"),
 ]
 unresolved_ids=set(unresolved.queue_event_id);deferred_ids=set(d.queue_event_id);blocked_ids=set(b.queue_event_id)
 checks.extend([
  ("TERMINAL_QUEUES_DISJOINT",deferred_ids.isdisjoint(blocked_ids),"deferred and blocked IDs must not overlap"),
  ("UNRESOLVED_FULLY_ACCOUNTED",unresolved_ids==deferred_ids|blocked_ids,f"unresolved={len(unresolved_ids)}, accounted={len(deferred_ids|blocked_ids)}"),
  ("BLOCK_REASON_PRESENT",len(b)==1 and b.blocking_items.ne("").all(),"blocked row requires blocking_items"),
 ])
 audit=pd.DataFrame([{"check":name,"status":"PASS" if ok else "FAIL","detail":detail} for name,ok,detail in checks]);passed=audit.status.eq("PASS").all();ap,sp=Path(audit_output_csv),Path(summary_json);ap.parent.mkdir(parents=True,exist_ok=True);audit.to_csv(ap,index=False,encoding="utf-8-sig")
 summary={"phase":"V3.2.1 Phase 6.26","release_gate":"PASS" if passed else "FAIL","checks_total":len(audit),"checks_passed":int(audit.status.eq("PASS").sum()),"input_rows":len(v),"status_counts":{k:int(counts.get(k,0)) for k in EXPECTED},"actionable_rows":len(a),"deferred_rows":len(d),"blocked_rows":len(b),"accounted_rows":len(v)-len(unresolved)+len(deferred_ids|blocked_ids),"audit_output_csv":str(ap),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
 if not passed:raise ValueError("Phase 6.26 release quality gate failed: "+", ".join(audit.loc[audit.status.eq("FAIL"),"check"]))
 return summary|{"summary_json":str(sp)}
