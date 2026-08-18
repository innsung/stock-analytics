import pandas as pd
from src.ml.phase610_kakao_games_subsidiary_capital_v321 import QUEUE_IDS,DOCS,audit_kakao_games_subsidiary_capital_v321
class Dart:
 def document_texts(self,r):
  issuer,shares=DOCS[r];name="Kakao Games Europe B.V." if issuer.endswith("EUROPE") else "주식회사 카카오게임즈"
  return [{"name":"x.xml","text":f"유상증자결정 종속회사의 주요경영사항 종속회사인 {name} 신주의 종류와 수 {shares}"}]
def test_resolves_kakao_games_subsidiary_capital_chain(tmp_path):
 pd.DataFrame({"queue_event_id":list(QUEUE_IDS)}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":r,"report_nm":"유상증자결정(종속회사의주요경영사항)"} for r in DOCS]).to_csv(tmp_path/"d.csv",index=False)
 result=audit_kakao_games_subsidiary_capital_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==3
