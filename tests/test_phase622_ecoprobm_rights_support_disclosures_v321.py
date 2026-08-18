import pandas as pd
from src.ml.phase622_ecoprobm_rights_support_disclosures_v321 import TARGETS,EXECUTION_QIDS,MARKET_QID,audit_ecoprobm_rights_support_disclosures_v321
def test_resolves_support_disclosures_and_preserves_market_event(tmp_path):
 q=[{"queue_event_id":MARKET_QID,"code":"247540","source_reference_date":"20220624","source_description":"권리락(무상증자)","resolution_status":"UNRESOLVED"}];d=[]
 for qid,(date,title,receipt,_) in TARGETS.items():q.append({"queue_event_id":qid,"code":"247540","source_reference_date":date,"source_description":title,"resolution_status":"UNRESOLVED"});d.append({"code":"247540","rcept_dt":date,"report_nm":title,"rcept_no":receipt,"flr_nm":"에코프로비엠"})
 pd.DataFrame(q).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame(d).to_csv(tmp_path/"d.csv",index=False);pd.DataFrame([{"queue_event_id":x,"verification_status":"NOT_APPLICABLE_EVIDENCE","official_disclosure_valid":"True"} for x in EXECUTION_QIDS]).to_csv(tmp_path/"p.csv",index=False)
 r=audit_ecoprobm_rights_support_disclosures_v321(actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),phase618_audit_csv=str(tmp_path/"p.csv"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert r["not_applicable_evidence_rows"]==2 and r["market_adjustment_preserved"]
