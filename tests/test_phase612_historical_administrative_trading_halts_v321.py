import pandas as pd
from src.ml.phase612_historical_administrative_trading_halts_v321 import TARGETS,audit_historical_administrative_trading_halts_v321
class Dart:
 def document_texts(self,r):
  reason=TARGETS[next(q for q,v in TARGETS.items() if v[1]==r)][2][0];return [{"name":"x.xml","text":f"매매거래정지 정지사유 {reason}"}]
def test_resolves_administrative_halts(tmp_path):
 pd.DataFrame({"queue_event_id":list(TARGETS)}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":v[1],"report_nm":"매매거래정지및정지해제(중요내용공시)"} for v in TARGETS.values()]).to_csv(tmp_path/"d.csv",index=False)
 result=audit_historical_administrative_trading_halts_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==4
