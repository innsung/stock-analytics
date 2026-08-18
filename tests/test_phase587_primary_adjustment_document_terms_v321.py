import pandas as pd

from src.ml.phase587_primary_adjustment_document_terms_v321 import extract_primary_adjustment_document_terms_v321


class Dart:
    def document_texts(self, receipt):
        return [{"name": "doc.xml", "text": "<table><tr><td>유상증자</td></tr><tr><td>신주배정기준일</td><td>2024-03-20</td></tr><tr><td>1주당 신주배정주식수 (주)</td><td>0.25</td></tr></table>"}]


def test_extracts_terms_from_unique_primary_document(tmp_path):
    pd.DataFrame([{"queue_event_id": "p1", "code": "006400", "source_reference_date": "20240110",
                  "source_description": "유상증자결정", "mechanic_family": "RIGHTS_OFFERING",
                  "execution_lane": "PRIMARY_ADJUSTMENT_DOCUMENT_REVIEW"}]).to_csv(tmp_path / "manifest.csv", index=False)
    pd.DataFrame([{"code": "006400", "rcept_dt": "20240110", "report_nm": "유상증자결정",
                  "rcept_no": "receipt"}]).to_csv(tmp_path / "disclosures.csv", index=False)
    pd.DataFrame(columns=["parent_queue_event_id", "parent_rcept_no", "controlling_mechanics_rcept_no"]).to_csv(tmp_path / "groups.csv", index=False)
    result = extract_primary_adjustment_document_terms_v321(
        Dart(), execution_manifest_csv=str(tmp_path / "manifest.csv"), disclosures_csv=str(tmp_path / "disclosures.csv"),
        legal_groups_csv=str(tmp_path / "groups.csv"), documents_dir=str(tmp_path / "docs"),
        output_csv=str(tmp_path / "out.csv"), review_queue_csv=str(tmp_path / "review.csv"),
        summary_json=str(tmp_path / "summary.json"))
    row = pd.read_csv(tmp_path / "out.csv", dtype=str).iloc[0]
    assert result["terms_extracted_rows"] == 1
    assert row["official_effective_date_candidate"] == "20240320"
    assert row["ratio_or_allotment_candidate"] == "0.25"
    assert row["promotion_status"].startswith("NOT_PROMOTED")
