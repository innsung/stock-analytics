import pandas as pd

from src.ml.phase563_direct_action_integration_v321 import integrate_direct_action_evidence_v321


def test_integrates_supporting_disclosure_but_keeps_core_unresolved(tmp_path):
    base = {"code":"1", "event_family":"CORPORATE_ACTION", "source_reference_date":"20250101",
            "source_description":"x", "resolution_status":"UNRESOLVED", "effective_date":"",
            "known_at":"", "action_type":"", "adjustment_factor":"", "cash_amount":"",
            "verification_source":"", "verification_reference":"", "resolution_note":""}
    pd.DataFrame([base | {"queue_event_id":"support"}, base | {"queue_event_id":"core"}]).to_csv(tmp_path / "v.csv", index=False)
    pd.DataFrame([{"queue_event_id":"support", "verification_source":"GROUP_REVIEW",
        "verification_reference":"r", "resolution_note":"same legal event"}]).to_csv(tmp_path / "e.csv", index=False)
    result = integrate_direct_action_evidence_v321(
        verification_csv=str(tmp_path / "v.csv"), evidence_csv=str(tmp_path / "e.csv"),
        output_csv=str(tmp_path / "o.csv"), audit_csv=str(tmp_path / "a.csv"),
        priority_output_csv=str(tmp_path / "p.csv"), priority_summary_json=str(tmp_path / "p.json"))
    out = pd.read_csv(tmp_path / "o.csv", dtype=str).set_index("queue_event_id")
    assert out.loc["support", "resolution_status"] == "NOT_APPLICABLE"
    assert out.loc["core", "resolution_status"] == "UNRESOLVED"
    assert result["unresolved_queue_events"] == 1
