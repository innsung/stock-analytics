import pandas as pd

from src.ml.phase562_direct_action_group_review_v321 import review_direct_action_groups_v321


def test_keeps_one_core_event_and_marks_supporting_and_treasury_rows(tmp_path):
    rights = tmp_path / "r.xml"; rights.write_text("rights", encoding="utf-8")
    treasury = tmp_path / "t.xml"; treasury.write_text("감자방법 자기주식 소각", encoding="utf-8")
    pd.DataFrame([
        {"queue_event_id":"a", "code":"1", "source_reference_date":"20250101", "source_description":"주요사항보고서(유상증자결정)", "action_family":"RIGHTS_OFFERING", "candidate_legal_event_group":"1:R", "rcept_no":"r1", "document_paths":str(rights)},
        {"queue_event_id":"b", "code":"1", "source_reference_date":"20250102", "source_description":"가격안내", "action_family":"RIGHTS_OFFERING", "candidate_legal_event_group":"1:R", "rcept_no":"r2", "document_paths":str(rights)},
        {"queue_event_id":"c", "code":"2", "source_reference_date":"20250103", "source_description":"감자", "action_family":"CAPITAL_REDUCTION", "candidate_legal_event_group":"2:C", "rcept_no":"r3", "document_paths":str(treasury)},
    ]).to_csv(tmp_path / "i.csv", index=False)
    result = review_direct_action_groups_v321(
        inventory_csv=str(tmp_path / "i.csv"), evidence_output_csv=str(tmp_path / "e.csv"),
        audit_output_csv=str(tmp_path / "a.csv"))
    assert result["not_applicable_evidence_rows"] == 2
    assert result["core_unresolved_rows"] == 1
