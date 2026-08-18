import io
import zipfile

import pandas as pd

from src.dart.client import DartClient
from src.ml.phase569_historical_dividend_decision_parser_v321 import (
    parse_dividend_decision_text, parse_historical_dividend_decisions_v321,
)


def test_document_texts_honors_declared_euc_kr_encoding():
    payload = '<meta content="text/html; charset=euc-kr"><p>현금배당 결정</p>'.encode("euc-kr")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("doc.xml", payload)

    class Response:
        content = archive.getvalue(); headers = {"content-type": "application/zip"}
        def raise_for_status(self): pass
    class Session:
        def get(self, *args, **kwargs): return Response()

    assert "현금배당 결정" in DartClient("key", Session()).document_texts("1")[0]["text"]


def test_parser_uses_last_corrected_terms():
    text = """<p>1주당 배당금(원) 보통주식 300 배당기준일 2024-03-31 이사회결의일(결정일) 2024-04-24</p>
    <p>1주당 배당금(원) 보통주식 1,304 배당기준일 2025-02-28 배당금지급 예정일자 2025-04-01
    이사회결의일(결정일) 2025-02-27</p>"""
    parsed = parse_dividend_decision_text(text)
    assert parsed["common_cash_dividend_per_share"] == "1304"
    assert parsed["dividend_record_date"] == "2025-02-28"
    assert parsed["board_decision_date"] == "2025-02-27"


def test_manifest_parser_does_not_promote_record_date(tmp_path):
    doc = tmp_path / "doc.xml"
    doc.write_text("1주당 배당금(원) 보통주식 500 배당기준일 2024-12-31 이사회결의일(결정일) 2025-02-01", encoding="utf-8")
    pd.DataFrame([{"queue_event_id":"q", "document_paths":str(doc), "acquisition_status":"ACQUIRED"}]).to_csv(tmp_path / "in.csv", index=False)
    result = parse_historical_dividend_decisions_v321(acquisition_csv=str(tmp_path / "in.csv"), output_csv=str(tmp_path / "out.csv"))
    out = pd.read_csv(tmp_path / "out.csv", dtype=str).fillna("")
    assert result["parsed_rows"] == 1
    assert out.loc[0, "strict_promotion_status"] == "NOT_PROMOTED_RECORD_DATE_IS_NOT_EX_DATE"
