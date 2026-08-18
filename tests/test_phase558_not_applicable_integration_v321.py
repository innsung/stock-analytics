import pandas as pd

from src.ml.phase558_not_applicable_integration_v321 import integrate_not_applicable_evidence_v321


def test_applies_only_explicit_evidence_and_preserves_terminal_rows(tmp_path):
    verification, evidence = tmp_path / "v.csv", tmp_path / "e.csv"
    base = {"code":"1", "event_family":"CORPORATE_ACTION", "source_reference_date":"20260101",
            "source_description":"x", "effective_date":"", "known_at":"", "action_type":"",
            "adjustment_factor":"", "cash_amount":"", "verification_source":"",
            "verification_reference":"", "resolution_note":""}
    pd.DataFrame([
        base | {"queue_event_id":"a", "resolution_status":"UNRESOLVED"},
        base | {"queue_event_id":"b", "resolution_status":"VERIFIED"},
    ]).to_csv(verification, index=False)
    pd.DataFrame([{"queue_event_id":"a", "verification_source":"DART",
        "verification_reference":"r", "resolution_note":"separate issuer"}]).to_csv(evidence, index=False)
    result = integrate_not_applicable_evidence_v321(
        verification_csv=str(verification), evidence_csv=str(evidence),
        output_csv=str(tmp_path / "out.csv"), audit_csv=str(tmp_path / "audit.csv"),
        priority_output_csv=str(tmp_path / "p.csv"), priority_summary_json=str(tmp_path / "p.json"))
    out = pd.read_csv(tmp_path / "out.csv", dtype=str)
    assert result["applied_rows"] == 1
    assert dict(zip(out.queue_event_id, out.resolution_status)) == {"a":"NOT_APPLICABLE", "b":"VERIFIED"}
    assert result["unresolved_queue_events"] == 0
