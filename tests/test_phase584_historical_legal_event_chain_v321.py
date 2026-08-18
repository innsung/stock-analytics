import pandas as pd

from src.ml.phase584_historical_legal_event_chain_v321 import build_historical_legal_event_chain_v321


def test_links_amendment_to_unique_prior_primary_and_deduplicates_receipt(tmp_path):
    manifest = pd.DataFrame([
        {"queue_event_id": "p1", "code": "6400", "source_reference_date": "20240110",
         "source_description": "유상증자결정", "document_role": "PRIMARY_OR_AMENDED_DECISION",
         "mechanic_family": "RIGHTS_OFFERING", "execution_lane": "PRIMARY_ADJUSTMENT_DOCUMENT_REVIEW"},
        {"queue_event_id": "a1", "code": "6400", "source_reference_date": "20240120",
         "source_description": "[기재정정]유상증자결정", "document_role": "AMENDMENT",
         "mechanic_family": "RIGHTS_OFFERING", "execution_lane": "CORPORATE_ACTION_LEGAL_EVENT_CHAIN"},
    ])
    manifest.to_csv(tmp_path / "manifest.csv", index=False)
    duplicate = {"code": "006400", "rcept_dt": "20240120", "report_nm": "[기재정정]유상증자결정",
                 "rcept_no": "20240120000001"}
    pd.DataFrame([duplicate, duplicate]).to_csv(tmp_path / "disclosures.csv", index=False)
    result = build_historical_legal_event_chain_v321(
        execution_manifest_csv=str(tmp_path / "manifest.csv"), disclosures_csv=str(tmp_path / "disclosures.csv"),
        output_csv=str(tmp_path / "out.csv"), review_queue_csv=str(tmp_path / "review.csv"),
        summary_json=str(tmp_path / "summary.json"))
    row = pd.read_csv(tmp_path / "out.csv", dtype=str).iloc[0]
    assert result["ready_for_semantic_validation"] == 1
    assert row["candidate_parent_queue_event_ids"] == "p1"
    assert row["child_rcept_no"] == "20240120000001"
    assert row["promotion_status"] == "NOT_PROMOTED_REQUIRES_ORIGINAL_DOCUMENT_SEMANTICS"


def test_fails_closed_without_parent(tmp_path):
    pd.DataFrame([{"queue_event_id": "a1", "code": "006400", "source_reference_date": "20240120",
                  "source_description": "[기재정정]유상증자결정", "document_role": "AMENDMENT",
                  "mechanic_family": "RIGHTS_OFFERING", "execution_lane": "CORPORATE_ACTION_LEGAL_EVENT_CHAIN"}]).to_csv(
                      tmp_path / "manifest.csv", index=False)
    pd.DataFrame([{"code": "006400", "rcept_dt": "20240120", "report_nm": "[기재정정]유상증자결정",
                   "rcept_no": "20240120000001"}]).to_csv(tmp_path / "disclosures.csv", index=False)
    result = build_historical_legal_event_chain_v321(
        execution_manifest_csv=str(tmp_path / "manifest.csv"), disclosures_csv=str(tmp_path / "disclosures.csv"),
        output_csv=str(tmp_path / "out.csv"), review_queue_csv=str(tmp_path / "review.csv"),
        summary_json=str(tmp_path / "summary.json"))
    assert result["manual_review_rows"] == 1
    assert pd.read_csv(tmp_path / "review.csv").loc[0, "parent_candidate_status"] == "NO_PARENT_CANDIDATE"
