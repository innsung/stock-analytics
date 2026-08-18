import pandas as pd

from src.ml.phase603_samsung_heavy_preferred_delisting_warning_v321 import TARGETS, audit_samsung_heavy_preferred_delisting_warnings_v321


class Dart:
    def document_texts(self, receipt):
        return [{"name": "x.xml", "text": "삼성중공업 1우선주 상장폐지 우려 예고 보통주 투자유의"}]


def test_resolves_preferred_share_warnings_as_common_share_na(tmp_path):
    pd.DataFrame({"queue_event_id": list(TARGETS)}).to_csv(tmp_path/"q.csv", index=False)
    pd.DataFrame([{"rcept_no": receipt,
        "report_nm": "투자유의안내(삼성중공업(주) 1우선주 상장폐지 우려 예고)"}
        for receipt in TARGETS.values()]).to_csv(tmp_path/"d.csv", index=False)
    result = audit_samsung_heavy_preferred_delisting_warnings_v321(Dart(),
        actionable_queue_csv=str(tmp_path/"q.csv"), disclosures_csv=str(tmp_path/"d.csv"),
        documents_dir=str(tmp_path/"docs"), evidence_output_csv=str(tmp_path/"e.csv"),
        audit_output_csv=str(tmp_path/"a.csv"), summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"] == 2
