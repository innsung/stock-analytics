import pandas as pd

from src.ml.phase602_kakao_overseas_dr_delisting_v321 import TARGETS, audit_kakao_overseas_dr_delisting_v321


class Dart:
    def document_texts(self, receipt):
        return [{"name": "x.xml", "text": "해외증권시장 싱가포르 GDR 상장폐지 2023년 05월 25일"}]


class Provider:
    def ohlcv(self, start, end, code, adjusted):
        return pd.DataFrame({"종가": [58000, 58200]}, index=pd.to_datetime(["2023-05-24", "2023-05-25"]))


def test_resolves_kakao_sgx_gdr_decision_and_completion(tmp_path):
    pd.DataFrame({"queue_event_id": list(TARGETS)}).to_csv(tmp_path/"q.csv", index=False)
    pd.DataFrame([{"rcept_no": receipt, "report_nm": "주요사항보고서(해외증권시장주권등상장폐지)"}
                  for receipt, _ in TARGETS.values()]).to_csv(tmp_path/"d.csv", index=False)
    result = audit_kakao_overseas_dr_delisting_v321(Dart(), Provider(), actionable_queue_csv=str(tmp_path/"q.csv"),
        disclosures_csv=str(tmp_path/"d.csv"), documents_dir=str(tmp_path/"docs"),
        evidence_output_csv=str(tmp_path/"e.csv"), audit_output_csv=str(tmp_path/"a.csv"), summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"] == 2
    assert result["domestic_krx_breakpoints"] == 0
