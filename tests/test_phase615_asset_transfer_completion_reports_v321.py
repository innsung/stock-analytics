import pandas as pd
from src.ml.phase615_asset_transfer_completion_reports_v321 import TARGETS,audit_asset_transfer_completion_reports_v321
class Dart:
 def document_texts(self,r):return [{"name":"x.xml","text":"합병등 종료보고서 대주주등 지분변동 상황 - 해당사항 없음 주식매수청구권 행사 - 해당사항 없음 신주배정 등에 관한 사항 - 해당사항 없음"}]
def test_resolves_asset_transfer_reports_with_no_holder_rights(tmp_path):
 pd.DataFrame({"queue_event_id":list(TARGETS)}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":v[1],"report_nm":"합병등종료보고서(자산양수도)"} for v in TARGETS.values()]).to_csv(tmp_path/"d.csv",index=False)
 result=audit_asset_transfer_completion_reports_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==4
