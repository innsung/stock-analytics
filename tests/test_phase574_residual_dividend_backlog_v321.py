import pandas as pd

from src.ml.phase574_residual_dividend_backlog_v321 import build_residual_dividend_backlog_v321


def test_classifies_residual_dividend_paths(tmp_path):
    pd.DataFrame([{"queue_event_id":"a", "code":"1", "workstream":"P3_RECENT_DIVIDEND_EVIDENCE",
                   "source_reference_date":"20250101", "source_description":"x"},
                  {"queue_event_id":"b", "code":"2", "workstream":"P3_RECENT_DIVIDEND_EVIDENCE",
                   "source_reference_date":"20250102", "source_description":"x"}]).to_csv(tmp_path / "q.csv", index=False)
    pd.DataFrame([{"queue_event_id":"a", "acquisition_status":"NO_DIRECT_DIVIDEND_DECISION_FOUND"},
                  {"queue_event_id":"b", "acquisition_status":"ACQUIRED"}]).to_csv(tmp_path / "a.csv", index=False)
    pd.DataFrame([{"queue_event_id":"b", "candidate_status":"LATE_DISCLOSURE_NOT_PIT_ELIGIBLE"}]).to_csv(tmp_path / "c.csv", index=False)
    pd.DataFrame(columns=["queue_event_id", "status"]).to_csv(tmp_path / "d.csv", index=False)
    result = build_residual_dividend_backlog_v321(actionable_queue_csv=str(tmp_path / "q.csv"),
        acquisition_csv=str(tmp_path / "a.csv"), candidates_csv=str(tmp_path / "c.csv"),
        discovery_audit_csv=str(tmp_path / "d.csv"), output_csv=str(tmp_path / "o.csv"), summary_json=str(tmp_path / "s.json"))
    out = pd.read_csv(tmp_path / "o.csv", dtype=str).set_index("queue_event_id")
    assert result["target_rows"] == 2
    assert out.loc["a", "residual_status"] == "NO_DIRECT_DIVIDEND_DECISION"
    assert out.loc["b", "residual_status"] == "DECISION_DISCLOSED_AFTER_EXDATE"
