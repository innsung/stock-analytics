import pandas as pd

from src.ml.phase566_actionable_backlog_router_v321 import route_actionable_resolution_backlog_v321


def test_routes_guarded_core_as_blocked_without_changing_resolution(tmp_path):
    pd.DataFrame([
        {"queue_event_id":"blocked", "workstream":"P2", "priority_order":2, "source_reference_date":"20260101", "code":"1"},
        {"queue_event_id":"next", "workstream":"P3", "priority_order":3, "source_reference_date":"20250101", "code":"2"},
    ]).to_csv(tmp_path / "q.csv", index=False)
    pd.DataFrame([{"queue_event_id":"blocked", "row_status":"CORE_EVENT_UNRESOLVED"}]).to_csv(tmp_path / "d.csv", index=False)
    pd.DataFrame([{"check_item":"SURVIVING_RULE", "evidence_status":"MISSING"}]).to_csv(tmp_path / "c.csv", index=False)
    result = route_actionable_resolution_backlog_v321(
        priority_queue_csv=str(tmp_path / "q.csv"), direct_action_audit_csv=str(tmp_path / "d.csv"),
        complex_evidence_audit_csv=str(tmp_path / "c.csv"), actionable_output_csv=str(tmp_path / "a.csv"),
        blocked_output_csv=str(tmp_path / "b.csv"), summary_json=str(tmp_path / "s.json"))
    assert result["blocked_rows"] == 1
    assert result["actionable_rows"] == 1
    assert result["next_actionable_target"] == "P3"
    assert result["resolution_status_changed"] is False
