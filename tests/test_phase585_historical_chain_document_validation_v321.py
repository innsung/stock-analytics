import pandas as pd

from src.ml.phase585_historical_chain_document_validation_v321 import validate_historical_chain_documents_v321


class Dart:
    def document_texts(self, receipt):
        text = "유상증자 정정 주요사항보고서" if receipt == "child" else "유상증자 결정 주요사항보고서"
        return [{"name": "doc.xml", "text": text}]


def test_validates_child_and_parent_semantics_without_promotion(tmp_path):
    pd.DataFrame([{"queue_event_id": "a1", "code": "006400", "document_role": "AMENDMENT",
                  "mechanic_family": "RIGHTS_OFFERING", "child_rcept_no": "child",
                  "candidate_parent_queue_event_ids": "p1",
                  "chain_status": "READY_FOR_ORIGINAL_DOCUMENT_SEMANTIC_VALIDATION"}]).to_csv(tmp_path / "chain.csv", index=False)
    pd.DataFrame([{"queue_event_id": "p1", "code": "006400", "source_reference_date": "20240110",
                  "source_description": "유상증자결정"}]).to_csv(tmp_path / "manifest.csv", index=False)
    pd.DataFrame([{"code": "006400", "rcept_dt": "20240110", "report_nm": "유상증자결정",
                  "rcept_no": "parent"}]).to_csv(tmp_path / "disclosures.csv", index=False)
    result = validate_historical_chain_documents_v321(
        Dart(), chain_csv=str(tmp_path / "chain.csv"), execution_manifest_csv=str(tmp_path / "manifest.csv"),
        disclosures_csv=str(tmp_path / "disclosures.csv"), documents_dir=str(tmp_path / "docs"),
        output_csv=str(tmp_path / "out.csv"), review_queue_csv=str(tmp_path / "review.csv"),
        summary_json=str(tmp_path / "summary.json"))
    row = pd.read_csv(tmp_path / "out.csv", dtype=str).iloc[0]
    assert result["semantic_chains_confirmed"] == 1
    assert row["promotion_status"] == "NOT_PROMOTED_PRIMARY_MECHANICS_STILL_UNRESOLVED"
    assert result["unique_receipts_processed"] == 2
