import pandas as pd

from src.ml.phase565_strict_evidence_integration_v321 import integrate_strict_event_evidence_v321


def test_integrates_strict_evidence_and_preserves_existing_terminal_rows(tmp_path):
    base = {"code":"000001", "event_family":"CORPORATE_ACTION", "source_reference_date":"20250101",
            "source_description":"x", "effective_date":"", "known_at":"", "action_type":"",
            "adjustment_factor":"", "cash_amount":"", "verification_source":"",
            "verification_reference":"", "resolution_note":""}
    pd.DataFrame([base | {"queue_event_id":"a", "resolution_status":"UNRESOLVED"},
                  base | {"queue_event_id":"b", "resolution_status":"NOT_APPLICABLE"}]).to_csv(tmp_path / "v.csv", index=False)
    pd.DataFrame([{"queue_event_id":"a", "code":"000001", "event_family":"CORPORATE_ACTION",
        "source_reference_date":"20250101", "effective_date":"20250102", "known_at":"20250101",
        "action_type":"RIGHTS", "adjustment_factor":1.1, "cash_amount":0,
        "verification_source":"KRX_DART", "verification_reference":"r", "resolution_note":"ok"}]).to_csv(tmp_path / "e.csv", index=False)
    result = integrate_strict_event_evidence_v321(
        verification_csv=str(tmp_path / "v.csv"), evidence_csv=str(tmp_path / "e.csv"),
        output_csv=str(tmp_path / "o.csv"), audit_csv=str(tmp_path / "a.csv"),
        priority_output_csv=str(tmp_path / "p.csv"), priority_summary_json=str(tmp_path / "p.json"))
    out = pd.read_csv(tmp_path / "o.csv", dtype=str).set_index("queue_event_id")
    assert out.loc["a", "resolution_status"] == "VERIFIED"
    assert out.loc["a", "action_type"] == "RIGHTS"
    assert out.loc["b", "resolution_status"] == "NOT_APPLICABLE"
    assert result["verified_queue_events"] == 1
