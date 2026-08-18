import pandas as pd
from src.ml.phase600_kakao_zero_ratio_merger_v321 import audit_kakao_zero_ratio_merger_v321
class Dart:
    def document_texts(self,r):return [{"name":"x.xml","text":"카카오스페이스 지분을 100% 합병비율은 1:0 합병신주를 발행하지 않는 별도의 합병교부금도 없습니다"}]
class Provider:
    def ohlcv(self,start,end,code,adjusted):return pd.DataFrame({"종가":[50000,50500]},index=pd.to_datetime(["2024-04-30","2024-05-02"]))
def test_resolves_kakao_zero_ratio_merger(tmp_path):
    pd.DataFrame([{"queue_event_id":"03f28f1f0e6e787d420a"}]).to_csv(tmp_path/"q.csv",index=False)
    r=audit_kakao_zero_ratio_merger_v321(Dart(),Provider(),actionable_queue_csv=str(tmp_path/"q.csv"),documents_dir=str(tmp_path/"d"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"))
    assert r["not_applicable_evidence_rows"]==1
