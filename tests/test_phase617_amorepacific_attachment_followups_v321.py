import pandas as pd
from src.ml.phase617_amorepacific_attachment_followups_v321 import TARGETS,audit_amorepacific_attachment_followups_v321
def test_resolves_attachment_followups_against_phase595(tmp_path):
 pd.DataFrame({"queue_event_id":list(TARGETS)}).to_csv(tmp_path/"q.csv",index=False);dis=[];cores=[]
 for _,(a,b,c,action,ratio) in TARGETS.items():
  title="회사합병결정" if action=="MERGER" else "주식교환ㆍ이전결정";dis.extend([{"rcept_no":a,"report_nm":"[첨부정정]주요사항보고서("+title+")"},{"rcept_no":b,"report_nm":"주요사항보고서("+title+")"}]);cores.append({"queue_event_id":c,"controlling_rcept_no":b,"action_type":action,"event_date":"20210901","transaction_ratio":ratio,"event_window_breakpoints":"0","listing_window_breakpoints":"0","verification_status":"NOT_APPLICABLE_EVIDENCE"})
 pd.DataFrame(dis).to_csv(tmp_path/"d.csv",index=False);pd.DataFrame(cores).to_csv(tmp_path/"c.csv",index=False)
 result=audit_amorepacific_attachment_followups_v321(actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),phase595_audit_csv=str(tmp_path/"c.csv"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==2
