import pandas as pd

from src.ml.phase557_subsidiary_applicability_parser_v321 import parse_subsidiary_action_applicability_v321


def test_separates_explicit_subsidiary_from_direct_issuer_action(tmp_path):
    sub, direct = tmp_path / "sub.xml", tmp_path / "direct.xml"
    sub.write_text("종속회사인 Example Sub 의 주요경영사항 신고", encoding="utf-8")
    direct.write_text("Listed Co 특수관계인의 유상증자 참여", encoding="utf-8")
    manifest = tmp_path / "m.csv"
    pd.DataFrame([
        {"queue_event_id":"a", "code":"1", "rcept_no":"r1", "status":"ACQUIRED", "document_paths":str(sub)},
        {"queue_event_id":"b", "code":"2", "rcept_no":"r2", "status":"ACQUIRED", "document_paths":str(direct)},
        {"queue_event_id":"c", "code":"3", "rcept_no":"", "status":"AMBIGUOUS_DISCLOSURES", "document_paths":""},
    ]).to_csv(manifest, index=False)
    result = parse_subsidiary_action_applicability_v321(
        acquisition_manifest_csv=str(manifest), audit_output_csv=str(tmp_path / "a.csv"),
        not_applicable_output_csv=str(tmp_path / "n.csv"))
    audit = pd.read_csv(tmp_path / "a.csv")
    assert result["not_applicable_evidence_rows"] == 1
    assert result["direct_issuer_review_rows"] == 1
    assert result["unresolved_rows"] == 1
    assert audit.iloc[0].promotion_status == "NOT_APPLICABLE_EVIDENCE"
