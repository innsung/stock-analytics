import pandas as pd
from src.ml.phase606_lgchem_historical_subsidiary_capital_v321 import GROUPS,audit_lgchem_historical_subsidiary_capital_v321
class Dart:
    def document_texts(self,r):return [{"name":"x.xml","text":"유상증자결정(종속회사의 주요경영사항) 종속회사인 Ultium Cells LLC 신주의 종류와 수"}]
def test_resolves_lgchem_historical_subsidiary_groups(tmp_path):
    ids=sorted({x for xs,_ in GROUPS.values() for x in xs});rs=sorted({x for _,xs in GROUPS.values() for x in xs})
    pd.DataFrame({"queue_event_id":ids}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":r,"report_nm":"유상증자결정(종속회사의주요경영사항)"} for r in rs]).to_csv(tmp_path/"d.csv",index=False)
    result=audit_lgchem_historical_subsidiary_capital_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"]==5
