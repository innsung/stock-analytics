import pandas as pd

from src.ml.phase560_residual_subsidiary_integration_v321 import integrate_residual_subsidiary_evidence_v321


def test_integrates_residual_evidence(tmp_path):
    base = {"code":"1", "event_family":"CORPORATE_ACTION", "source_reference_date":"20260101",
            "source_description":"support", "resolution_status":"UNRESOLVED", "effective_date":"",
            "known_at":"", "action_type":"", "adjustment_factor":"", "cash_amount":"",
            "verification_source":"", "verification_reference":"", "resolution_note":""}
    pd.DataFrame([base | {"queue_event_id":"q"}]).to_csv(tmp_path / "v.csv", index=False)
    pd.DataFrame([{"queue_event_id":"q", "verification_source":"DART_LINK",
        "verification_reference":"a|b", "resolution_note":"supporting notice"}]).to_csv(tmp_path / "e.csv", index=False)
    result = integrate_residual_subsidiary_evidence_v321(
        verification_csv=str(tmp_path / "v.csv"), evidence_csv=str(tmp_path / "e.csv"),
        output_csv=str(tmp_path / "o.csv"), audit_csv=str(tmp_path / "a.csv"),
        priority_output_csv=str(tmp_path / "p.csv"), priority_summary_json=str(tmp_path / "p.json"))
    assert result["phase"] == "V3.2.1 Phase 5.60"
    assert result["not_applicable_queue_events"] == 1
    assert result["unresolved_queue_events"] == 0
