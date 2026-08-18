import pandas as pd

from src.ml.phase592_capital_reduction_applicability_v321 import audit_historical_capital_reductions_v321


def test_excludes_confirmed_subsidiary_reduction(tmp_path):
    pd.DataFrame([{"queue_event_id": "q", "code": "005930", "mechanic_family": "CAPITAL_REDUCTION",
                  "controlling_mechanics_rcept_no": "r", "ratio_or_allotment_candidate": "80",
                  "extraction_status": "TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION"}]).to_csv(tmp_path / "t.csv", index=False)
    pd.DataFrame([{"queue_event_id": "q", "source_description": "감자결정(종속회사의 주요경영사항)"}]).to_csv(tmp_path / "m.csv", index=False)
    (tmp_path / "docs").mkdir(); (tmp_path / "docs" / "r_00.xml").write_text("무상감자 감자방법", encoding="utf-8")
    result = audit_historical_capital_reductions_v321(
        terms_csv=str(tmp_path / "t.csv"), execution_manifest_csv=str(tmp_path / "m.csv"),
        documents_dir=str(tmp_path / "docs"), evidence_output_csv=str(tmp_path / "e.csv"),
        audit_output_csv=str(tmp_path / "a.csv"), summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 1
    assert pd.read_csv(tmp_path / "a.csv").loc[0, "reduction_type"] == "FREE_REDUCTION"
