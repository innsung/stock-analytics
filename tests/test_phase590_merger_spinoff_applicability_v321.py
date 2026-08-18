import sqlite3

import pandas as pd

from src.ml.phase590_merger_spinoff_applicability_v321 import audit_historical_merger_spinoff_applicability_v321


def test_excludes_no_new_share_merger_but_keeps_material_merger(tmp_path):
    pd.DataFrame([
        {"queue_event_id": "n", "code": "005930", "source_reference_date": "20200101",
         "mechanic_family": "MERGER", "controlling_mechanics_rcept_no": "r1",
         "official_effective_date_candidate": "20200201", "extraction_status": "TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION"},
        {"queue_event_id": "m", "code": "005930", "source_reference_date": "20200101",
         "mechanic_family": "MERGER", "controlling_mechanics_rcept_no": "r2",
         "official_effective_date_candidate": "20200201", "extraction_status": "TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION"},
    ]).to_csv(tmp_path / "terms.csv", index=False)
    pd.DataFrame([{"queue_event_id": "n", "source_description": "회사합병결정"},
                  {"queue_event_id": "m", "source_description": "회사합병결정"}]).to_csv(tmp_path / "manifest.csv", index=False)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "r1_00.xml").write_text("무증자합병 신주를 발행하지 아니함 합병신주 0", encoding="utf-8")
    (tmp_path / "docs" / "r2_00.xml").write_text("합병신주를 교부한다", encoding="utf-8")
    with sqlite3.connect(tmp_path / "prices.db") as conn:
        pd.DataFrame({"code": ["005930"], "date": ["2020-01-02"]}).to_sql("stock_prices", conn, index=False)
    result = audit_historical_merger_spinoff_applicability_v321(
        terms_csv=str(tmp_path / "terms.csv"), execution_manifest_csv=str(tmp_path / "manifest.csv"),
        documents_dir=str(tmp_path / "docs"), trading_calendar_db=str(tmp_path / "prices.db"),
        evidence_output_csv=str(tmp_path / "e.csv"), audit_output_csv=str(tmp_path / "a.csv"),
        summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 1
    assert pd.read_csv(tmp_path / "e.csv").loc[0, "queue_event_id"] == "n"
    assert result["material_or_reparse_rows"] == 1
