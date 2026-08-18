import pandas as pd

from src.ml.phase561_direct_action_document_inventory_v321 import build_direct_action_document_inventory_v321


class FakeDart:
    def document_texts(self, receipt):
        return [{"name":"x.xml", "text":"official"}]


def test_reuses_prior_and_acquires_only_missing_documents(tmp_path):
    pd.DataFrame([
        {"queue_event_id":"a", "code":"1", "source_reference_date":"20260101", "source_description":"유상증자결정", "workstream":"P2_RECENT_DIRECT_ACTION_REVIEW"},
        {"queue_event_id":"b", "code":"1", "source_reference_date":"20260102", "source_description":"유상증자신주발행가액", "workstream":"P2_RECENT_DIRECT_ACTION_REVIEW"},
    ]).to_csv(tmp_path / "q.csv", index=False)
    old = tmp_path / "old.xml"; old.write_text("old", encoding="utf-8")
    pd.DataFrame([{"queue_event_id":"a", "status":"ACQUIRED", "rcept_no":"r1", "document_paths":str(old)}]).to_csv(tmp_path / "prior.csv", index=False)
    pd.DataFrame([{"code":"1", "rcept_dt":"20260102", "report_nm":"유상증자신주발행가액", "rcept_no":"r2"}]).to_csv(tmp_path / "d.csv", index=False)
    result = build_direct_action_document_inventory_v321(
        FakeDart(), priority_queue_csv=str(tmp_path / "q.csv"), disclosures_csv=str(tmp_path / "d.csv"),
        prior_acquisition_csv=str(tmp_path / "prior.csv"), documents_dir=str(tmp_path / "docs"),
        output_csv=str(tmp_path / "out.csv"))
    assert result["reused_rows"] == 1
    assert result["acquired_rows"] == 1
    assert result["candidate_legal_event_groups"] == 1
