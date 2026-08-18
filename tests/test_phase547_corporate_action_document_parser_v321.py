import pandas as pd

from src.ml.phase547_corporate_action_document_parser_v321 import parse_corporate_action_documents_v321


def test_flags_known_at_after_allotment_date(tmp_path):
    doc, acquisition, output = tmp_path / "d.xml", tmp_path / "a.csv", tmp_path / "o.csv"
    doc.write_text("<table><tr><td>8. 신주배정기준일</td><td>2025년 04월 11일</td></tr>"
                   "<tr><td>9. 1주당 신주배정주식수 (주)</td><td>0.14</td></tr></table>", encoding="utf-8")
    pd.DataFrame([{"queue_event_id": "q", "code": "6400", "rcept_no": "r",
        "source_reference_date": "20250430", "action_type_hint": "RIGHTS",
        "document_paths": str(doc)}]).to_csv(acquisition, index=False)
    result = parse_corporate_action_documents_v321(acquisition_csv=str(acquisition), output_csv=str(output))
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["allotment_record_date"] == "20250411"
    assert row["market_check_eligibility"] == "KNOWN_AT_AFTER_EVENT_DATE"
    assert result["parsed_rows"] == 1
