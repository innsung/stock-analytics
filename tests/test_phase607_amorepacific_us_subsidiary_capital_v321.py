import pandas as pd
from src.ml.phase607_amorepacific_us_subsidiary_capital_v321 import QUEUE_IDS,RECEIPTS,audit_amorepacific_us_subsidiary_capital_v321
class Dart:
    def document_texts(self,r):return [{"name":"x.xml","text":"유상증자결정(종속회사의 주요경영사항) 종속회사인 Amorepacific US Investment, Inc. 신주의 종류와 수 1,000,000"}]
def test_resolves_amorepacific_us_base_correction_chain(tmp_path):
    pd.DataFrame({"queue_event_id":list(QUEUE_IDS)}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":r,"report_nm":"[기재정정]유상증자결정(종속회사의주요경영사항)"} for r in RECEIPTS]).to_csv(tmp_path/"d.csv",index=False)
    result=audit_amorepacific_us_subsidiary_capital_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"]==2 and result["chain_documents"]==3
