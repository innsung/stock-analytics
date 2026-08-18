import pandas as pd

from src.ml.phase543_recent_corporate_action_classifier_v321 import classify_recent_corporate_actions_v321


def test_separates_direct_and_subsidiary_actions(tmp_path):
    source, output, summary = tmp_path / "q.csv", tmp_path / "o.csv", tmp_path / "s.json"
    pd.DataFrame([
        {"queue_event_id": "a", "code": "68270", "source_reference_date": "20260521",
         "source_description": "주요사항보고서(무상증자결정)", "resolution_priority": "P2_RECENT_CORPORATE_ACTION"},
        {"queue_event_id": "b", "code": "51910", "source_reference_date": "20260225",
         "source_description": "유상증자결정(종속회사의주요경영사항)", "resolution_priority": "P2_RECENT_CORPORATE_ACTION"},
    ]).to_csv(source, index=False)
    result = classify_recent_corporate_actions_v321(
        priority_queue_csv=str(source), output_csv=str(output), summary_json=str(summary))
    rows = pd.read_csv(output, dtype=str).set_index("queue_event_id")
    assert rows.loc["a", "acquisition_priority"] == "P1_DIRECT_ISSUER_ACTION"
    assert rows.loc["b", "acquisition_priority"] == "P3_REVIEW_NOT_APPLICABLE"
    assert result["auto_promoted_rows"] == 0
