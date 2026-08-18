import pandas as pd

from src.ml.phase597_lgchem_subsidiary_rights_v321 import TARGETS, audit_lgchem_subsidiary_rights_v321


class Dart:
    def document_texts(self, receipt):
        return [{"name": "report.xml", "text": "유상증자결정(종속회사의 주요경영사항) 당사 종속회사인 ㈜LG에너지솔루션의 LG Energy Solution Michigan, Inc.에 대한 출자결정"}]


def test_resolves_only_explicit_subsidiary_capital_increases(tmp_path):
    pd.DataFrame([{"queue_event_id": q} for q in TARGETS]).to_csv(tmp_path/"q.csv", index=False)
    pd.DataFrame([{"rcept_no": r} for r in TARGETS.values()]).to_csv(tmp_path/"d.csv", index=False)
    result = audit_lgchem_subsidiary_rights_v321(
        Dart(), actionable_queue_csv=str(tmp_path/"q.csv"), disclosures_csv=str(tmp_path/"d.csv"),
        documents_dir=str(tmp_path/"docs"), evidence_output_csv=str(tmp_path/"e.csv"),
        audit_output_csv=str(tmp_path/"a.csv"), summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"] == 2
    assert len(pd.read_csv(tmp_path/"e.csv")) == 2
