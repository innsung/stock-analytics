import pandas as pd
from src.ml.phase611_naver_line_overseas_delisting_v321 import TARGETS,audit_naver_line_overseas_delisting_v321
class Dart:
 def document_texts(self,r):return [{"name":"x.xml","text":"종속회사의 주요경영사항 LINE Corporation 상장폐지 동경증권거래소 뉴욕증권거래소 243,715,542 2020년 12월 29일"}]
class Provider:
 def ohlcv(self,start,end,code,adjusted):return pd.DataFrame({"종가":[280000,282000]},index=pd.to_datetime(["2020-12-28","2020-12-29"]))
def test_resolves_line_overseas_delisting_without_naver_breakpoint(tmp_path):
 pd.DataFrame({"queue_event_id":list(TARGETS)}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":r,"report_nm":"해외증권시장주권등상장폐지(종속회사의주요경영사항)"} for r in TARGETS.values()]).to_csv(tmp_path/"d.csv",index=False)
 result=audit_naver_line_overseas_delisting_v321(Dart(),Provider(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==2 and result["naver_krx_breakpoints"]==0
