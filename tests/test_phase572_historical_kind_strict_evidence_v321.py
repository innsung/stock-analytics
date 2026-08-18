import pandas as pd

from src.ml.phase572_historical_kind_strict_evidence_v321 import build_historical_kind_strict_evidence_v321


class Response:
    encoding="utf-8"; apparent_encoding="utf-8"
    text="<p>회사우 결산배당락 종목 3. 적용일 : 2025. 3. 28</p>"
    def raise_for_status(self): pass
class Session:
    def get(self, *args, **kwargs): return Response()


def test_promotes_verified_preferred_share_amount(tmp_path):
    pd.DataFrame([{"queue_event_id":"q", "code":"000002", "company_name":"회사",
        "candidate_ex_date":"20250328", "kind_acpt_no":"20250327000001", "kind_doc_no":"20250327000002",
        "market_source_url":"https://kind.krx.co.kr/external/2025/03/27/x.htm"}]).to_csv(tmp_path / "d.csv", index=False)
    base = {"queue_event_id":"q", "corp_code":"corp", "rcept_no":"r", "rcept_dt":"20250201",
        "common_cash_dividend_per_share":"1000", "preferred_cash_dividend_per_share":"1050",
        "dividend_record_date":"2025-03-31", "board_decision_date":"2025-02-01", "parse_status":"PARSED_DECISION_TERMS"}
    pd.DataFrame([base | {"code":"000001"}, base | {"code":"000002"}]).to_csv(tmp_path / "p.csv", index=False)
    result = build_historical_kind_strict_evidence_v321(discovery_csv=str(tmp_path / "d.csv"),
        parsed_decisions_csv=str(tmp_path / "p.csv"), output_csv=str(tmp_path / "o.csv"),
        audit_csv=str(tmp_path / "a.csv"), session=Session())
    out = pd.read_csv(tmp_path / "o.csv")
    assert result["strict_rows"] == 1
    assert out.loc[0, "cash_amount"] == 1050
    assert str(out.loc[0, "effective_date"]) == "20250328"


def test_keeps_original_filing_available_before_later_correction(tmp_path):
    pd.DataFrame([{"queue_event_id":"q", "code":"000001", "company_name":"회사우",
        "candidate_ex_date":"20250321", "kind_acpt_no":"20250320000001", "kind_doc_no":"20250320000002",
        "market_source_url":"https://kind.krx.co.kr/external/2025/03/20/x.htm"}]).to_csv(tmp_path / "d.csv", index=False)
    base={"queue_event_id":"q","code":"000001","corp_code":"c","common_cash_dividend_per_share":"5000",
        "preferred_cash_dividend_per_share":"","dividend_record_date":"2025-03-24","board_decision_date":"2025-01-23",
        "parse_status":"PARSED_DECISION_TERMS"}
    pd.DataFrame([base|{"rcept_no":"20250123000001","rcept_dt":"20250123"},
                  base|{"rcept_no":"20250324000001","rcept_dt":"20250324"}]).to_csv(tmp_path / "p.csv",index=False)
    class R:
        encoding="utf-8"; apparent_encoding="utf-8"; text="회사우 4. 적용일 2025-03-21"
        def raise_for_status(self): pass
    class S:
        def get(self,*a,**k): return R()
    result=build_historical_kind_strict_evidence_v321(discovery_csv=str(tmp_path/"d.csv"),
        parsed_decisions_csv=str(tmp_path/"p.csv"),output_csv=str(tmp_path/"o.csv"),audit_csv=str(tmp_path/"a.csv"),session=S())
    assert result["strict_rows"] == 1
    assert pd.read_csv(tmp_path/"o.csv").loc[0,"cash_amount"] == 5000
