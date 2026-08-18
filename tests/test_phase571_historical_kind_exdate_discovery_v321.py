import pandas as pd

from src.ml.phase571_historical_kind_exdate_discovery_v321 import discover_historical_kind_exdates_v321


class Response:
    def __init__(self, text): self.text=text; self.encoding="utf-8"; self.apparent_encoding="utf-8"
    def raise_for_status(self): pass
class Session:
    def __init__(self): self.headers={}
    def post(self, *args, **kwargs):
        return Response("<dt class='img'><span class='subject'><a onclick=\"x('20250226000001','20250226000002')\">배당락 기준 가격 안내</a></span></dt>")
    def get(self, url, *args, **kwargs):
        if "searchContents" in url: return Response("https://kind.krx.co.kr/external/a")
        if "/external/" in url: return Response("<p>테스트회사 결산 배당락 종목</p>")
        return Response("")
class Dart:
    def stock_name_map(self): return {"000001":"테스트회사"}


def test_discovers_unique_official_notice_without_promoting(tmp_path):
    pd.DataFrame([{"queue_event_id":"q", "code":"1", "calendar_prior_trading_day_1":"20250227",
                   "candidate_status":"READY_FOR_OFFICIAL_MARKET_VERIFICATION"}]).to_csv(tmp_path / "in.csv", index=False)
    result = discover_historical_kind_exdates_v321(Dart(), candidates_csv=str(tmp_path / "in.csv"),
        output_csv=str(tmp_path / "out.csv"), audit_csv=str(tmp_path / "audit.csv"), session=Session())
    out = pd.read_csv(tmp_path / "out.csv", dtype=str).fillna("")
    assert result["discovered_rows"] == 1
    assert out.loc[0, "kind_doc_no"] == "20250226000002"
    assert out.loc[0, "strict_promotion_status"] == "NOT_PROMOTED_NOTICE_BODY_PARSE_REQUIRED"
