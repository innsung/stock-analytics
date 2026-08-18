import sqlite3

import pandas as pd

from src.ml.phase593_incomplete_primary_applicability_v321 import audit_incomplete_primary_adjustments_v321


def test_excludes_subsidiary_and_preserves_direct_review(tmp_path):
    pd.DataFrame([
        {"queue_event_id": "s", "code": "005930", "source_reference_date": "20210101",
         "mechanic_family": "RIGHTS_OFFERING", "controlling_mechanics_rcept_no": "r1",
         "extraction_status": "MECHANIC_CONFIRMED_EFFECTIVE_TERMS_INCOMPLETE"},
        {"queue_event_id": "d", "code": "005930", "source_reference_date": "20210101",
         "mechanic_family": "RIGHTS_OFFERING", "controlling_mechanics_rcept_no": "r2",
         "extraction_status": "MECHANIC_CONFIRMED_EFFECTIVE_TERMS_INCOMPLETE"},
    ]).to_csv(tmp_path / "t.csv", index=False)
    pd.DataFrame([{"queue_event_id": "s", "source_description": "유상증자결정(종속회사의 주요경영사항)"},
                  {"queue_event_id": "d", "source_description": "주요사항보고서(유상증자결정)"}]).to_csv(tmp_path / "m.csv", index=False)
    (tmp_path / "docs").mkdir()
    for receipt in ("r1", "r2"): (tmp_path / "docs" / f"{receipt}_00.xml").write_text("유상증자", encoding="utf-8")
    with sqlite3.connect(tmp_path / "p.db") as conn:
        pd.DataFrame({"code": ["005930"], "date": ["2020-01-02"]}).to_sql("stock_prices", conn, index=False)
    result = audit_incomplete_primary_adjustments_v321(
        terms_csv=str(tmp_path / "t.csv"), execution_manifest_csv=str(tmp_path / "m.csv"),
        documents_dir=str(tmp_path / "docs"), trading_calendar_db=str(tmp_path / "p.db"),
        evidence_output_csv=str(tmp_path / "e.csv"), review_output_csv=str(tmp_path / "r.csv"),
        audit_output_csv=str(tmp_path / "a.csv"), summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 1
    assert result["direct_reparse_rows"] == 1
    assert pd.read_csv(tmp_path / "r.csv").loc[0, "queue_event_id"] == "d"
