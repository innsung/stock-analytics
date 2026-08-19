
import importlib
from pathlib import Path
import pandas as pd

from src.ml.phase516_kind_crosscheck_v321 import (
    _extract_kind_doc_no,
    _extract_kind_document_url,
    _search_kind_disclosures,
    discover_kodex_next_hops_v321,
)


def test_extract_kind_doc_no_from_selected_main_document():
    html = """
    <select id="mainDoc" name="mainDoc">
      <option value="20260527009999|N">attachment</option>
      <option value="20260527001263|Y" selected="selected">main</option>
    </select>
    """
    assert _extract_kind_doc_no(html) == "20260527001263"


def test_extract_kind_doc_no_falls_back_to_first_document_value():
    html = '<option value="20260527001263&#124;Y">main</option>'
    assert _extract_kind_doc_no(html) == "20260527001263"


def test_extract_kind_document_url_from_search_contents():
    html = """<script>parent.setPath('',
    'https://kind.krx.co.kr/external/2026/04/22/000788/20260422002195/61500.htm',
    '/external/server/path','01','30');</script>"""
    assert _extract_kind_document_url(html).endswith("/61500.htm")


def test_search_kind_disclosures_uses_stock_code_and_date():
    class Response:
        text = """<a onclick="openDisclsViewer('20260422000788','')"
        title='현금ㆍ현물 배당 결정'>현금ㆍ현물 배당 결정</a>"""

        def raise_for_status(self):
            return None

    class Session:
        def post(self, url, **kwargs):
            assert kwargs["data"]["repIsuSrtCd"] == "A000660"
            assert kwargs["data"]["fromDate"] == "2026-04-22"
            assert kwargs["data"]["toDate"] == "2026-04-22"
            return Response()

    result = _search_kind_disclosures(
        Session(), code="660", disclosure_date="20260422", timeout=5
    )
    assert result == [{
        "kind_acpt_no": "20260422000788",
        "title": "현금ㆍ현물 배당 결정",
    }]


def test_crosscheck_classifies_krx_failover_as_retryable(tmp_path, monkeypatch):
    from src.ml.phase516_kind_crosscheck_v321 import crosscheck_kind_dividend_disclosures_v321

    queue = tmp_path / "queue.csv"
    output = tmp_path / "output.csv"
    audit = tmp_path / "audit.csv"
    pd.DataFrame([{
        "queue_event_id": "q1",
        "code": "660",
        "candidate_cash_amount": "1000",
        "record_date": "2026-05-31",
        "known_at": "2026-04-22",
        "official_document_reference": "20260422800788",
        "priority": "P1_RECORD_DATE_READY_FOR_MARKET_VERIFICATION",
    }]).to_csv(queue, index=False)

    class Response:
        status_code = 200
        url = "https://upgrade-notice.krx.co.kr/failover/index.html"
        text = "maintenance"

        def raise_for_status(self):
            return None

    class Session:
        def post(self, *args, **kwargs):
            class SearchResponse:
                text = """<a onclick="openDisclsViewer('20260422800788','')"
                title='현금ㆍ현물 배당 결정'>dividend</a>"""

                def raise_for_status(self):
                    return None
            return SearchResponse()

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("src.ml.phase516_kind_crosscheck_v321.requests.Session", Session)
    crosscheck_kind_dividend_disclosures_v321(
        market_exdate_queue_csv=str(queue),
        output_csv=str(output),
        audit_csv=str(audit),
    )

    result = pd.read_csv(output, dtype=str).fillna("").iloc[0]
    assert result["kind_status"] == "KRX_SERVICE_UNAVAILABLE"
    assert result["kind_retryable"] == "True"
    assert result["kind_http_status"] == "200"
    assert "upgrade-notice.krx.co.kr" in result["kind_final_url"]


def test_crosscheck_rejects_blank_kind_viewer_as_success(tmp_path, monkeypatch):
    from src.ml.phase516_kind_crosscheck_v321 import crosscheck_kind_dividend_disclosures_v321

    queue = tmp_path / "queue.csv"
    output = tmp_path / "output.csv"
    audit = tmp_path / "audit.csv"
    pd.DataFrame([{
        "queue_event_id": "q1",
        "code": "660",
        "candidate_cash_amount": "1000",
        "record_date": "2026-05-31",
        "known_at": "2026-04-22",
        "official_document_reference": "20260422800788",
        "priority": "P1_RECORD_DATE_READY_FOR_MARKET_VERIFICATION",
    }]).to_csv(queue, index=False)

    class Response:
        status_code = 200
        url = "https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno=20260422800788"
        text = "<title>close</title><script>location.href='/common/blank.html';</script>"

        def raise_for_status(self):
            return None

    class Session:
        def post(self, *args, **kwargs):
            class SearchResponse:
                text = """<a onclick="openDisclsViewer('20260422800788','')"
                title='현금ㆍ현물 배당 결정'>dividend</a>"""

                def raise_for_status(self):
                    return None
            return SearchResponse()

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("src.ml.phase516_kind_crosscheck_v321.requests.Session", Session)
    crosscheck_kind_dividend_disclosures_v321(
        market_exdate_queue_csv=str(queue),
        output_csv=str(output),
        audit_csv=str(audit),
    )

    result = pd.read_csv(output, dtype=str).fillna("").iloc[0]
    assert result["kind_status"] == "KIND_DOCUMENT_UNAVAILABLE"
    assert result["kind_retryable"] == "False"
    assert result["kind_doc_no"] == ""


def test_next_hop_discovery(tmp_path):
    bodies=tmp_path/"bodies"; bodies.mkdir()
    (bodies/"x.html").write_text(
        '<script>var url="/etf/product/distributionList.do"; $.ajax({url:"/api/etf/dist"});</script>',
        encoding="utf-8"
    )
    result=discover_kodex_next_hops_v321(
        bodies_dir=str(bodies),
        output_csv=str(tmp_path/"out.csv")
    )
    assert result["next_hops"] >= 1
    f=pd.read_csv(tmp_path/"out.csv")
    assert any("dist" in x.lower() for x in f["next_hop"].astype(str))


def test_kind_cli_namespace_contains_phase516_function():
    m=importlib.import_module("src.cli.kind_commands")
    assert hasattr(m,"crosscheck_kind_dividend_disclosures_v321")
