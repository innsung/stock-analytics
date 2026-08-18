import pandas as pd

from src.ml.phase555_current_resolution_priority_v321 import prioritize_current_resolution_backlog_v321


def test_prioritizes_recent_subsidiary_applicability_without_promotion(tmp_path):
    source = tmp_path / "in.csv"
    pd.DataFrame([
        {"queue_event_id":"a", "code":"1", "event_family":"CORPORATE_ACTION",
         "source_reference_date":"20260101", "source_description":"종속회사의 주요경영사항",
         "resolution_status":"UNRESOLVED", "resolution_note":"x"},
        {"queue_event_id":"b", "code":"2", "event_family":"DIVIDEND_OR_DISTRIBUTION",
         "source_reference_date":"20250101", "source_description":"dividend",
         "resolution_status":"UNRESOLVED", "resolution_note":"x"},
        {"queue_event_id":"c", "code":"3", "event_family":"CORPORATE_ACTION",
         "source_reference_date":"20260101", "source_description":"done",
         "resolution_status":"VERIFIED", "resolution_note":""},
    ]).to_csv(source, index=False)
    result = prioritize_current_resolution_backlog_v321(
        resolved_verification_csv=str(source), output_csv=str(tmp_path / "out.csv"),
        summary_json=str(tmp_path / "summary.json"))
    out = pd.read_csv(tmp_path / "out.csv", dtype=str)
    assert list(out.queue_event_id) == ["a", "b"]
    assert out.iloc[0].workstream == "P1_SUBSIDIARY_APPLICABILITY_REVIEW"
    assert set(out.auto_promotion_status) == {"NOT_PROMOTED_REQUIRES_EVIDENCE"}
    assert result["next_target_rows"] == 1
