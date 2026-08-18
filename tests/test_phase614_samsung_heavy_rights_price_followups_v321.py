import pandas as pd
from src.ml.phase614_samsung_heavy_rights_price_followups_v321 import TARGETS,audit_samsung_heavy_rights_price_followups_v321
class Dart:
 def document_texts(self,r):return [{"name":"x.xml","text":"유상증자 신주발행가액 1차 발행가액 확정 발행가액 5,130"}]
def test_resolves_price_notices_against_verified_core(tmp_path):
 pd.DataFrame({"queue_event_id":list(TARGETS)}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":r,"report_nm":"유상증자신주발행가액(안내공시)"} for r in TARGETS.values()]).to_csv(tmp_path/"d.csv",index=False)
 pd.DataFrame([{"queue_event_id":"5432bce5e1925c59ed3b","decision_rcept_no":"20211028000438","first_price_rcept_no":"20210914800549","record_date":"20210917","allotment_ratio":"0.331043387","first_issue_price":"5130.0","final_issue_price":"5130.0","effective_date":"20210916","adjustment_factor":"1.067524115755627","verification_status":"STRICT_RIGHTS_EVIDENCE_READY"}]).to_csv(tmp_path/"core.csv",index=False)
 result=audit_samsung_heavy_rights_price_followups_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),phase594_audit_csv=str(tmp_path/"core.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==2
