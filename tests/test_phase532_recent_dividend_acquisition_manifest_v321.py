import pandas as pd

from src.ml.phase532_recent_dividend_acquisition_manifest_v321 import build_recent_dividend_acquisition_manifest_v321


def test_builds_fail_closed_acquisition_statuses(tmp_path):
    q, d, s, out, summary = [tmp_path / n for n in ("q.csv", "d.csv", "s.csv", "o.csv", "j.json")]
    pd.DataFrame([
        {"queue_event_id": "a", "code": "660", "resolution_priority": "P1_RECENT_DIVIDEND", "source_reference_date": "20250301"},
        {"queue_event_id": "b", "code": "5930", "resolution_priority": "P1_RECENT_DIVIDEND", "source_reference_date": "20250302"},
    ]).to_csv(q, index=False)
    pd.DataFrame([{"code": "660", "flr_nm": "SK하이닉스", "known_at": "20260422",
                  "report_nm": "현금배당", "rcept_no": "20260422000001"}]).to_csv(d, index=False)
    pd.DataFrame([{"code": "660"}]).to_csv(s, index=False)
    result = build_recent_dividend_acquisition_manifest_v321(
        priority_queue_csv=str(q), decision_disclosures_csv=str(d), strict_evidence_csv=str(s),
        output_csv=str(out), summary_json=str(summary))
    rows = pd.read_csv(out, dtype=str).set_index("code")
    assert rows.loc["000660", "acquisition_status"] == "STRICT_EVIDENCE_ALREADY_AVAILABLE"
    assert rows.loc["005930", "acquisition_status"] == "NEEDS_COMPANY_DISCLOSURE_DISCOVERY"
    assert result["target_rows"] == 2
