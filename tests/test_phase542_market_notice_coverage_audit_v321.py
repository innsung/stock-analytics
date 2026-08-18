import pandas as pd

from src.ml.phase542_market_notice_coverage_audit_v321 import audit_market_notice_coverage_v321


def test_marks_uncovered_without_promoting(tmp_path):
    acquisition, strict, discovery = [tmp_path / x for x in ("a.csv", "s.csv", "d.csv")]
    output, summary = tmp_path / "out.csv", tmp_path / "summary.json"
    pd.DataFrame([{"queue_event_id": "q", "code": "5930", "flr_nm": "삼성전자",
                   "acquisition_status": "READY_FOR_KIND_MARKET_SEARCH"}]).to_csv(acquisition, index=False)
    pd.DataFrame(columns=["code"]).to_csv(strict, index=False)
    pd.DataFrame(columns=["code", "discovery_status"]).to_csv(discovery, index=False)
    result = audit_market_notice_coverage_v321(
        acquisition_manifest_csv=str(acquisition), strict_evidence_csv=str(strict),
        discovery_csvs=[str(discovery)], output_csv=str(output), summary_json=str(summary))
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["coverage_status"] == "NO_OFFICIAL_MARKET_NOTICE_FOUND_IN_SEARCH_SCOPE"
    assert row["promotion_status"] == "NOT_PROMOTED_WITHOUT_OFFICIAL_NOTICE"
    assert result["fail_closed"] is True
