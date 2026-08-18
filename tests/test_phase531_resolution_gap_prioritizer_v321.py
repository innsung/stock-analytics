import json

import pandas as pd

from src.ml.phase531_resolution_gap_prioritizer_v321 import prioritize_resolution_gaps_v321


def test_prioritizes_recent_dividends_and_excludes_verified(tmp_path):
    source, output, summary = tmp_path / "in.csv", tmp_path / "out.csv", tmp_path / "summary.json"
    pd.DataFrame([
        {"queue_event_id": "a", "code": "660", "event_family": "DIVIDEND_OR_DISTRIBUTION",
         "source_reference_date": "20260101", "source_description": "recent", "resolution_status": "UNRESOLVED"},
        {"queue_event_id": "b", "code": "5930", "event_family": "CORPORATE_ACTION",
         "source_reference_date": "20200101", "source_description": "old", "resolution_status": "UNRESOLVED"},
        {"queue_event_id": "c", "code": "5380", "event_family": "DIVIDEND_OR_DISTRIBUTION",
         "source_reference_date": "20250101", "source_description": "done", "resolution_status": "VERIFIED"},
    ]).to_csv(source, index=False)
    result = prioritize_resolution_gaps_v321(
        resolved_verification_csv=str(source), output_csv=str(output), summary_json=str(summary))
    rows = pd.read_csv(output, dtype=str)
    assert list(rows["queue_event_id"]) == ["a", "b"]
    assert rows.iloc[0]["resolution_priority"] == "P1_RECENT_DIVIDEND"
    assert result["unresolved_rows"] == 2
    assert json.loads(summary.read_text(encoding="utf-8"))["fail_closed"] is True
