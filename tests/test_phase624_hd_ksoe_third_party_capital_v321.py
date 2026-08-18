import pandas as pd
from src.ml.phase624_hd_ksoe_third_party_capital_v321 import audit_hd_ksoe_third_party_capital_v321
class Dart:
 def document_texts(self,r):return [{"name":"x.xml","text":'<TE ACODE="CST_CNT">6,099,570</TE><TE ACODE="PST_CNT">9,118,231</TE><TE ACODE="PST_ISS_VAL">137,088</TE><TE ACODE="PART">한국산업은행</TE><TE ACODE="ALL_CNT">-</TE>'}]
def test_resolves_exact_third_party_preferred_capital_raise(tmp_path):
 pd.DataFrame([{"queue_event_id":"cb08d9456cf27879002a","code":"009540","source_reference_date":"20210630","source_description":"[기재정정]주요사항보고서(유상증자결정)"}]).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"code":"009540","rcept_dt":"20210630","report_nm":"[기재정정]주요사항보고서(유상증자결정)","rcept_no":"20210630000881","flr_nm":"HD한국조선해양"}]).to_csv(tmp_path/"d.csv",index=False)
 r=audit_hd_ksoe_third_party_capital_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert r["not_applicable_evidence_rows"]==1
