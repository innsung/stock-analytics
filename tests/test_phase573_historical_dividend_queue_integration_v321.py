import pandas as pd

from src.ml.phase573_historical_dividend_queue_integration_v321 import integrate_historical_dividend_evidence_v321


def test_selects_latest_event_and_preserves_ledger_history(tmp_path):
    base = {"queue_event_id":"q", "code":"000001", "event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20250301", "source_description":"annual", "resolution_status":"UNRESOLVED",
        "effective_date":"", "known_at":"", "action_type":"", "adjustment_factor":"", "cash_amount":"",
        "verification_source":"", "verification_reference":"", "resolution_note":""}
    pd.DataFrame([base]).to_csv(tmp_path / "v.csv", index=False)
    evidence = {"queue_event_id":"q", "code":"000001", "event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20250331", "action_type":"CASH_DIVIDEND", "adjustment_factor":1,
        "verification_source":"DART+KIND", "verification_reference":"r", "resolution_note":"strict"}
    pd.DataFrame([evidence | {"effective_date":"20240329", "known_at":"20240328", "cash_amount":500},
                  evidence | {"effective_date":"20250328", "known_at":"20250327", "cash_amount":600}]).to_csv(tmp_path / "e.csv", index=False)
    result = integrate_historical_dividend_evidence_v321(
        verification_csv=str(tmp_path / "v.csv"), strict_ledger_csv=str(tmp_path / "e.csv"),
        selected_evidence_csv=str(tmp_path / "s.csv"), selection_audit_csv=str(tmp_path / "sa.csv"),
        output_csv=str(tmp_path / "o.csv"), integration_audit_csv=str(tmp_path / "ia.csv"),
        priority_output_csv=str(tmp_path / "p.csv"), priority_summary_json=str(tmp_path / "p.json"))
    out = pd.read_csv(tmp_path / "o.csv", dtype=str).fillna("")
    audit = pd.read_csv(tmp_path / "sa.csv", dtype=str).fillna("")
    assert result["selected_queue_rows"] == 1 and result["ledger_only_rows"] == 1
    assert out.loc[0, "cash_amount"] == "600"
    assert "PRESERVED_IN_STRICT_LEDGER_NOT_QUEUE_SUMMARY" in set(audit["selection_status"])
