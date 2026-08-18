import pandas as pd
from src.ml.phase621_historical_amendment_duplicates_v321 import TARGETS,audit_historical_amendment_duplicates_v321
def test_resolves_exact_amendments_with_locked_chain(tmp_path):
 q=[];d=[];c=[];v=[]
 for qid,(code,date,title,receipt,parent,parent_receipt,anchor) in TARGETS.items():
  q.append({"queue_event_id":qid,"code":code,"source_reference_date":date,"source_description":title});d.append({"code":code,"rcept_dt":date,"report_nm":title,"rcept_no":receipt});c.append({"queue_event_id":qid,"child_rcept_no":receipt,"candidate_parent_count":"1","candidate_parent_queue_event_ids":parent,"parent_candidate_status":"UNIQUE_PARENT_CANDIDATE"});v.append({"queue_event_id":anchor,"resolution_status":"NOT_APPLICABLE"})
 pd.DataFrame(q).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame(d).to_csv(tmp_path/"d.csv",index=False);pd.DataFrame(c).to_csv(tmp_path/"c.csv",index=False);pd.DataFrame(v).drop_duplicates().to_csv(tmp_path/"v.csv",index=False)
 r=audit_historical_amendment_duplicates_v321(actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),chain_csv=str(tmp_path/"c.csv"),verification_csv=str(tmp_path/"v.csv"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert r["not_applicable_evidence_rows"]==3
