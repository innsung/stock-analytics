import pandas as pd

from src.ml.phase529_kind_market_search_v321 import discover_kind_market_exdate_notices_v321


def test_discovers_common_share_notice(tmp_path, monkeypatch):
    candidates = tmp_path / "candidates.csv"
    output, audit = tmp_path / "output.csv", tmp_path / "audit.csv"
    pd.DataFrame([{"code": "5380", "company_name": "현대자동차",
                   "expected_record_date": "20260531"}]).to_csv(candidates, index=False)

    class Response:
        status_code = 200
        encoding = "utf-8"
        apparent_encoding = "utf-8"
        def __init__(self, text=""): self.text = text
        def raise_for_status(self): return None

    search = '''<dt class="img"><strong class="name">현대자동차</strong>
      <span class="subject"><a onclick="openDisclsViewer('20260527000558','20260527001266')">중간(분기) 배당락 기준 가격 안내</a></span></dt>'''
    monkeypatch.setattr("requests.Session.get", lambda self, url, **kw:
        Response("parent.setPath('', 'https://kind.krx.co.kr/external/2026/05/27/x.htm', '')")
        if "searchContents" in url else Response())
    monkeypatch.setattr("requests.Session.post", lambda *a, **k: Response(search))
    result = discover_kind_market_exdate_notices_v321(
        candidates_csv=str(candidates), output_csv=str(output), audit_csv=str(audit))
    assert result["discovered_rows"] == 1
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["code"] == "005380"
    assert row["kind_acpt_no"] == "20260527000558"
