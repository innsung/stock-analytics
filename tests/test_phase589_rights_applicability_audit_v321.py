import pandas as pd

from src.ml.phase589_rights_applicability_audit_v321 import audit_historical_rights_applicability_v321


def test_excludes_subsidiary_and_third_party_but_not_shareholder_rights(tmp_path):
    terms = []
    manifest = []
    for qid, receipt, description in [("s", "r1", "유상증자결정(자회사의 주요경영사항)"),
                                      ("t", "r2", "주요사항보고서(유상증자결정)"),
                                      ("h", "r3", "주요사항보고서(유상증자결정)")]:
        terms.append({"queue_event_id": qid, "code": "005930", "mechanic_family": "RIGHTS_OFFERING",
                      "controlling_mechanics_rcept_no": receipt,
                      "extraction_status": "TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION"})
        manifest.append({"queue_event_id": qid, "source_description": description})
    pd.DataFrame(terms).to_csv(tmp_path / "terms.csv", index=False)
    pd.DataFrame(manifest).to_csv(tmp_path / "manifest.csv", index=False)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "r1_00.xml").write_text("유상증자", encoding="utf-8")
    (tmp_path / "docs" / "r2_00.xml").write_text("증자방식 제3자배정", encoding="utf-8")
    (tmp_path / "docs" / "r3_00.xml").write_text("증자방식 주주배정", encoding="utf-8")
    result = audit_historical_rights_applicability_v321(
        terms_csv=str(tmp_path / "terms.csv"), execution_manifest_csv=str(tmp_path / "manifest.csv"),
        documents_dir=str(tmp_path / "docs"), evidence_output_csv=str(tmp_path / "e.csv"),
        audit_output_csv=str(tmp_path / "a.csv"), summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 2
    assert result["shareholder_rights_terp_candidates"] == 1
    assert set(pd.read_csv(tmp_path / "e.csv")["queue_event_id"]) == {"s", "t"}
