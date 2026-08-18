import pandas as pd

from src.ml.phase546_corporate_action_document_acquisition_v321 import acquire_missing_corporate_action_documents_v321


def test_acquires_exact_disclosure_document(tmp_path):
    manifest, disclosures, output = tmp_path / "m.csv", tmp_path / "d.csv", tmp_path / "o.csv"
    pd.DataFrame([{"queue_event_id": "q", "code": "660", "source_reference_date": "20260706",
        "source_description": "[기재정정]주요사항보고서(유상증자결정)", "action_type_hint": "RIGHTS",
        "acquisition_status": "OFFICIAL_CANDIDATE_ACQUISITION_REQUIRED"}]).to_csv(manifest, index=False)
    pd.DataFrame([{"code": "660", "rcept_dt": "20260706",
        "report_nm": "[기재정정]주요사항보고서(유상증자결정)", "rcept_no": "20260706000403"}]).to_csv(disclosures, index=False)
    class Client:
        def document_texts(self, rcept_no): return [{"name": "doc.xml", "text": "official"}]
    result = acquire_missing_corporate_action_documents_v321(
        Client(), candidate_manifest_csv=str(manifest), disclosures_csv=str(disclosures),
        documents_dir=str(tmp_path / "docs"), output_csv=str(output))
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["rcept_no"] == "20260706000403"
    assert row["status"] == "ACQUIRED"
    assert result["acquired_rows"] == 1
