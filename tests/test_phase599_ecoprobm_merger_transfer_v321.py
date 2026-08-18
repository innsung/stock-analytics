import pandas as pd
from src.ml.phase599_ecoprobm_merger_transfer_v321 import audit_ecoprobm_merger_transfer_v321

class Dart:
    def document_texts(self,r):
        texts={"20240326000614":"에코프로글로벌 지분 100% 1 : 0.0000000 합병 신주를 발행하지 않는",
        "20240603000252":"합병기일 2024.05.30 합병비율은 1: 0 신주를 발행하지 않습니다",
        "20240227900523":"상장폐지승인을위한의안상정결정 유가증권시장상장 코스닥시장 상장폐지"}
        return [{"name":"x.xml","text":texts[r]}]
class Provider:
    def ohlcv(self,start,end,code,adjusted):
        return pd.DataFrame({"종가":[200000,201000]},index=pd.to_datetime(["2024-05-29","2024-05-30"]))
def test_resolves_merger_chain_and_transfer_proposal(tmp_path):
    ids=["6684ffeaa6e0f5358f4b","9425dbaa6796b905188a","0caa1e190a1b397dcee0"]
    pd.DataFrame([{"queue_event_id":x} for x in ids]).to_csv(tmp_path/"q.csv",index=False)
    r=audit_ecoprobm_merger_transfer_v321(Dart(),Provider(),actionable_queue_csv=str(tmp_path/"q.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"))
    assert r["not_applicable_evidence_rows"]==3
