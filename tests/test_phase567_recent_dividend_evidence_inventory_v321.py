import pandas as pd

from src.ml.phase567_recent_dividend_evidence_inventory_v321 import build_recent_dividend_evidence_inventory_v321


def test_rejects_future_strict_event_as_link_for_older_disclosure(tmp_path):
    pd.DataFrame([{"queue_event_id":"q", "code":"1", "source_reference_date":"20250315",
        "source_description":"annual fact", "workstream":"P3_RECENT_DIVIDEND_EVIDENCE"}]).to_csv(tmp_path / "q.csv", index=False)
    pd.DataFrame([{"queue_event_id":"q", "coverage_status":"STRICT_EVIDENCE_AVAILABLE"}]).to_csv(tmp_path / "c.csv", index=False)
    pd.DataFrame([{"code":"1", "effective_date":"20260330", "verification_reference":"future"}]).to_csv(tmp_path / "s.csv", index=False)
    result = build_recent_dividend_evidence_inventory_v321(
        actionable_queue_csv=str(tmp_path / "q.csv"), prior_coverage_audit_csv=str(tmp_path / "c.csv"),
        strict_evidence_csvs=[str(tmp_path / "s.csv")], output_csv=str(tmp_path / "o.csv"),
        summary_json=str(tmp_path / "sum.json"))
    row = pd.read_csv(tmp_path / "o.csv", dtype=str).fillna("").iloc[0]
    assert row.inventory_status == "CORRECTED_HISTORICAL_MARKET_SEARCH_REQUIRED"
    assert row.linkable_strict_dates == ""
    assert row.future_non_linkable_dates == "20260330"
    assert result["auto_promoted_rows"] == 0
