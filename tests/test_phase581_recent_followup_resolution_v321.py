import pandas as pd

from src.ml.phase581_recent_followup_resolution_v321 import resolve_recent_followups_v321


class Dart:
    def document_texts(self, receipt):
        return [{"name":"doc.xml","text":"삼성SDI 유상증자 청약결과 ※관련공시 2025-05-19 유상증자결정"}]


def test_links_followup_to_verified_primary_rights_event(tmp_path):
    pd.DataFrame([{"queue_event_id":"cec6598232cfffeb0da1","code":"006400","workstream":"P4_RECENT_FOLLOWUP_REVIEW"}]).to_csv(tmp_path/"q.csv",index=False)
    pd.DataFrame([{"code":"006400","action_type":"RIGHTS","resolution_status":"VERIFIED","verification_reference":"primary"}]).to_csv(tmp_path/"r.csv",index=False)
    result=resolve_recent_followups_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),resolved_verification_csv=str(tmp_path/"r.csv"),
        documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"))
    assert result["not_applicable_evidence_rows"] == 1
    assert "primary" in pd.read_csv(tmp_path/"e.csv").loc[0,"verification_reference"]
