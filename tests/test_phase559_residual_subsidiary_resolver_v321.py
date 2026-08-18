import pandas as pd

from src.ml.phase559_residual_subsidiary_resolver_v321 import resolve_residual_subsidiary_actions_v321


class FakeDart:
    def document_texts(self, receipt):
        text = "특수관계인의 유상증자 참여" if receipt == "support" else "[종속회사에 관한 사항] 종속회사명 Sub"
        return [{"name":"x.xml", "text":text}]


def test_resolves_support_notice_and_all_subsidiary_ambiguous_set(tmp_path):
    pd.DataFrame([
        {"queue_event_id":"a", "code":"1", "rcept_no":"support", "document_status":"ACQUIRED", "semantic_status":"DIRECT_LISTED_ISSUER_ACTION_REQUIRES_REVIEW"},
        {"queue_event_id":"b", "code":"2", "rcept_no":"", "document_status":"AMBIGUOUS_DISCLOSURES", "semantic_status":"UNRESOLVED"},
    ]).to_csv(tmp_path / "audit.csv", index=False)
    pd.DataFrame([
        {"queue_event_id":"a", "source_reference_date":"20260102", "error":""},
        {"queue_event_id":"b", "source_reference_date":"20260103", "error":"r2|r3"},
    ]).to_csv(tmp_path / "acq.csv", index=False)
    pd.DataFrame([{"code":"1", "report_nm":"주요사항보고서(유상증자결정)",
        "rcept_dt":"20260101", "rcept_no":"main"}]).to_csv(tmp_path / "d.csv", index=False)
    result = resolve_residual_subsidiary_actions_v321(
        FakeDart(), applicability_audit_csv=str(tmp_path / "audit.csv"),
        acquisition_manifest_csv=str(tmp_path / "acq.csv"), disclosures_csv=str(tmp_path / "d.csv"),
        documents_dir=str(tmp_path / "docs"), evidence_output_csv=str(tmp_path / "e.csv"),
        audit_output_csv=str(tmp_path / "o.csv"))
    assert result["not_applicable_evidence_rows"] == 2
    assert result["unresolved_rows"] == 0
