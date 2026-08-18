import pandas as pd

from src.ml.phase568_historical_dividend_decision_acquisition_v321 import acquire_historical_dividend_decisions_v321


class FakeDart:
    def corp_code_map(self): return {"000001":"corp"}
    def disclosure_list(self, corp, start, end, page_count):
        return [{"rcept_no":"r1", "rcept_dt":"20241220", "report_nm":"현금ㆍ현물배당결정"},
                {"rcept_no":"r2", "rcept_dt":"20241221", "report_nm":"현금ㆍ현물배당결정(자회사의 주요경영사항)"}]
    def document_texts(self, receipt): return [{"name":"x.xml", "text":"official"}]


def test_acquires_only_direct_parent_dividend_decisions(tmp_path):
    pd.DataFrame([{"queue_event_id":"q", "code":"1", "corrected_search_start":"20240101",
        "corrected_search_end":"20250331", "inventory_status":"CORRECTED_HISTORICAL_MARKET_SEARCH_REQUIRED"}]).to_csv(tmp_path / "i.csv", index=False)
    result = acquire_historical_dividend_decisions_v321(
        FakeDart(), inventory_csv=str(tmp_path / "i.csv"), documents_dir=str(tmp_path / "docs"),
        output_csv=str(tmp_path / "o.csv"))
    out = pd.read_csv(tmp_path / "o.csv")
    assert result["queue_rows_with_candidates"] == 1
    assert result["candidate_documents_acquired"] == 1
    assert list(out.rcept_no) == ["r1"]
