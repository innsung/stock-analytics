import pandas as pd
from src.ml.phase616_physical_split_business_transfer_completions_v321 import TARGETS,audit_physical_split_business_transfer_completions_v321
class Dart:
 def document_texts(self,r):
  kind=next(v[2] for v in TARGETS.values() if v[1]==r);body="물적분할 신설회사 주식을 분할되는 회사에 100% 배정 최대주주 지분율 변동은 없습니다" if kind=="PHYSICAL_SPLIT" else "영업양수 해당사항 없음 당사가 발행할 신주 및 지급할 교부금은 없습니다"
  return [{"name":"x.xml","text":"합병등 종료보고서 대주주등 지분변동 상황 신주배정 등에 관한 사항 "+body}]
def test_resolves_physical_split_and_business_transfer_completions(tmp_path):
 pd.DataFrame({"queue_event_id":list(TARGETS)}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":v[1],"report_nm":"합병등종료보고서(분할)"} for v in TARGETS.values()]).to_csv(tmp_path/"d.csv",index=False)
 result=audit_physical_split_business_transfer_completions_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==5
