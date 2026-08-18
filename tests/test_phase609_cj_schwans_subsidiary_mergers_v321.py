import pandas as pd
from src.ml.phase609_cj_schwans_subsidiary_mergers_v321 import QUEUE_IDS,DOCS,audit_cj_schwans_subsidiary_mergers_v321
class Dart:
 def document_texts(self,r):
  s=DOCS[r];return [{"name":"x.xml","text":"회사합병 결정 종속회사의 주요경영사항 "+s["ratio"]+" "+" ".join(s["terms"])}]
def test_resolves_cj_schwans_internal_merger_group(tmp_path):
 pd.DataFrame({"queue_event_id":list(QUEUE_IDS)}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":r,"report_nm":"회사합병결정(종속회사의주요경영사항)"} for r in DOCS]).to_csv(tmp_path/"d.csv",index=False)
 result=audit_cj_schwans_subsidiary_mergers_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==2
