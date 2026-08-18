import pandas as pd

from src.ml.phase544_corporate_action_candidate_manifest_v321 import build_corporate_action_candidate_manifest_v321


def test_matches_candidate_by_code_action_and_receipt_date(tmp_path):
    queue, candidates, output, summary = [tmp_path / x for x in ("q.csv", "c.csv", "o.csv", "s.json")]
    pd.DataFrame([{"queue_event_id": "q", "code": "68270", "source_reference_date": "20260521",
        "source_description": "주요사항보고서(무상증자결정)", "acquisition_priority": "P1_DIRECT_ISSUER_ACTION"}]).to_csv(queue, index=False)
    pd.DataFrame([{"code": "68270", "action_type_hint": "BONUS", "rcept_no": "20260521000101",
        "event_kind": "BONUS_ISSUE_DECISION", "official_known_at": "2026년 05월 21일",
        "official_event_date": "2026년 06월 05일", "verification_source": "DART",
        "verification_reference": "20260521000101"}]).to_csv(candidates, index=False)
    result = build_corporate_action_candidate_manifest_v321(
        classified_queue_csv=str(queue), official_candidates_csv=str(candidates),
        output_csv=str(output), summary_json=str(summary))
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["candidate_rcept_no"] == "20260521000101"
    assert row["acquisition_status"] == "OFFICIAL_CANDIDATE_AVAILABLE"
    assert result["auto_promoted_rows"] == 0
