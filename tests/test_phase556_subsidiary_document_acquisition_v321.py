import pandas as pd

from src.ml.phase556_subsidiary_document_acquisition_v321 import acquire_subsidiary_action_documents_v321


class FakeDart:
    def document_texts(self, receipt):
        return [{"name": f"{receipt}.xml", "text": "official"}]


def test_acquires_unique_match_and_quarantines_ambiguous(tmp_path):
    queue, disclosures = tmp_path / "q.csv", tmp_path / "d.csv"
    pd.DataFrame([
        {"queue_event_id":"a", "code":"1", "source_reference_date":"20260101",
         "source_description":" subsidiary action ", "workstream":"P1_SUBSIDIARY_APPLICABILITY_REVIEW"},
        {"queue_event_id":"b", "code":"2", "source_reference_date":"20260102",
         "source_description":"same", "workstream":"P1_SUBSIDIARY_APPLICABILITY_REVIEW"},
    ]).to_csv(queue, index=False)
    pd.DataFrame([
        {"code":"1", "rcept_dt":"20260101", "report_nm":"subsidiaryaction", "rcept_no":"r1"},
        {"code":"2", "rcept_dt":"20260102", "report_nm":"same", "rcept_no":"r2"},
        {"code":"2", "rcept_dt":"20260102", "report_nm":"same", "rcept_no":"r3"},
    ]).to_csv(disclosures, index=False)
    result = acquire_subsidiary_action_documents_v321(
        FakeDart(), priority_queue_csv=str(queue), disclosures_csv=str(disclosures),
        documents_dir=str(tmp_path / "docs"), output_csv=str(tmp_path / "out.csv"))
    out = pd.read_csv(tmp_path / "out.csv")
    assert result["acquired_rows"] == 1
    assert result["ambiguous_rows"] == 1
    assert list(out.status) == ["ACQUIRED", "AMBIGUOUS_DISCLOSURES"]
    assert len(list((tmp_path / "docs").glob("*.xml"))) == 1
