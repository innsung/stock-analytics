import pandas as pd

from src.ml.phase598_hdhyundai_exchangeable_bond_v321 import audit_hdhyundai_exchangeable_bond_v321


class Dart:
    def document_texts(self, receipt):
        if receipt == "20241011000438":
            text = "교환에 관한 사항 사채발행방법 사모 에이치디현대일렉트릭 주식회사 717,125 교환가액 369,531"
        else:
            text = "사모 교환사채 실제발행주식수(주) - 실제발행금액(원) 265,000,000,000 납입일 2024-11-11"
        return [{"name": "report.xml", "text": text}]


class Provider:
    def ohlcv(self, start, end, code, adjusted):
        return pd.DataFrame({"종가": [80000, 81000, 80500]},
                            index=pd.to_datetime(["2024-11-08", "2024-11-11", "2024-11-12"]))


def test_resolves_subsidiary_share_exchangeable_bond(tmp_path):
    pd.DataFrame([{"queue_event_id": "1567271747690326bc6b"}]).to_csv(tmp_path/"q.csv", index=False)
    result = audit_hdhyundai_exchangeable_bond_v321(
        Dart(), Provider(), actionable_queue_csv=str(tmp_path/"q.csv"), documents_dir=str(tmp_path/"docs"),
        evidence_output_csv=str(tmp_path/"e.csv"), audit_output_csv=str(tmp_path/"a.csv"),
        summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"] == 1
