import pandas as pd

from src.ml.phase526_kind_document_parser_v321 import (
    parse_kind_dividend_document,
    parse_kind_dividend_documents_v321,
)


HTML = """
<table>
<tr><td>1. 배당구분</td><td>분기배당</td></tr>
<tr><td>2. 배당종류</td><td>현금배당</td></tr>
<tr><td>3. 1주당 배당금(원)</td><td>보통주식</td><td>1,500</td></tr>
<tr><td>종류주식</td><td>1,550</td></tr>
<tr><td>4. 시가배당률(%)</td><td>보통주식</td><td>1.1</td></tr>
<tr><td>종류주식</td><td>1.2</td></tr>
<tr><td>5. 배당금총액(원)</td><td>123,456,789</td></tr>
<tr><td>6. 배당기준일</td><td>2026-05-31</td></tr>
<tr><td>7. 배당금지급 예정일자</td><td>2026-06-30</td></tr>
<tr><td>10. 이사회결의일(결정일)</td><td>2026-04-22</td></tr>
</table>
"""


def test_parse_kind_dividend_document():
    result = parse_kind_dividend_document(HTML)
    assert result["common_cash_amount"] == "1500"
    assert result["preferred_cash_amount"] == "1550"
    assert result["record_date"] == "20260531"
    assert result["payment_date"] == "20260630"
    assert result["board_date"] == "20260422"
    assert result["parse_status"] == "SUCCESS"


def test_parse_kind_dividend_documents_writes_csv(tmp_path):
    docs = tmp_path / "documents"
    docs.mkdir()
    (docs / "20260422000788_20260422002195.html").write_text(HTML, encoding="utf-8")
    output = tmp_path / "parsed.csv"
    result = parse_kind_dividend_documents_v321(documents_dir=str(docs), output_csv=str(output))
    assert result["status_counts"] == {"SUCCESS": 1}
    row = pd.read_csv(output, dtype=str).fillna("").iloc[0]
    assert row["kind_acpt_no"] == "20260422000788"
    assert row["common_cash_amount"] == "1500"
