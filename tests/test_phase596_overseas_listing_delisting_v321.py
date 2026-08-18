import pandas as pd

from src.ml.phase596_overseas_listing_delisting_v321 import audit_overseas_listing_delistings_v321, TARGETS


class Dart:
    def document_texts(self, receipt):
        return [{"name": "report.xml", "text": "<p>해외증권시장 상장폐지 룩셈부르크 DR 주식예탁증서</p>"}]


class Provider:
    def ohlcv(self, start, end, code, adjusted):
        index = pd.to_datetime(["2024-12-18", "2024-12-19", "2025-03-28", "2025-03-31"])
        return pd.DataFrame({"종가": [200000, 201000, 60000, 61000]}, index=index)


def test_resolves_overseas_dr_delistings_without_domestic_breakpoint(tmp_path):
    pd.DataFrame([{"queue_event_id": q} for q in TARGETS]).to_csv(tmp_path / "q.csv", index=False)
    pd.DataFrame([{"rcept_no": receipt, "report_nm": "주요사항보고서(해외증권시장주권등상장폐지)"}
                  for _, receipt, _, _ in TARGETS.values()]).to_csv(tmp_path / "d.csv", index=False)
    result = audit_overseas_listing_delistings_v321(
        Dart(), Provider(), actionable_queue_csv=str(tmp_path / "q.csv"), disclosures_csv=str(tmp_path / "d.csv"),
        documents_dir=str(tmp_path / "docs"), evidence_output_csv=str(tmp_path / "e.csv"),
        audit_output_csv=str(tmp_path / "a.csv"), summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 3
    assert len(pd.read_csv(tmp_path / "e.csv")) == 3
