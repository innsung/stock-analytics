
import importlib
from pathlib import Path
import pandas as pd

from src.ml.phase512_resolvers_v321 import (
    build_stock_dividend_exdate_resolution_queue_v321,
)


def test_build_stock_dividend_exdate_queue_unique(tmp_path):
    refined=tmp_path/"refined.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","source_reference_date":"20230307",
        "candidate_cash_amount":"361","candidate_known_at":"20230307",
    }]).to_csv(refined,index=False)
    decisions=tmp_path/"decisions.csv"
    pd.DataFrame([{
        "code":"005930","known_at":"20221215","report_nm":"현금ㆍ현물배당 결정",
        "rcept_no":"202212150001","verification_source":"OPENDART_DISCLOSURE_LIST",
    }]).to_csv(decisions,index=False)
    result=build_stock_dividend_exdate_resolution_queue_v321(
        refined_amount_candidates_csv=str(refined),
        dividend_decisions_csv=str(decisions),
        output_csv=str(tmp_path/"out.csv"),
        match_days=430,
    )
    assert result["rows"]==1
    out=pd.read_csv(tmp_path/"out.csv",dtype=str).fillna("")
    assert out.iloc[0]["decision_match_status"]=="UNIQUE_DECISION_DISCLOSURE"
    assert out.iloc[0]["effective_date"]==""
    assert out.iloc[0]["resolution_status"]=="UNRESOLVED"


def test_exdate_queue_keeps_ambiguity(tmp_path):
    refined=tmp_path/"refined.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","source_reference_date":"20230307",
        "candidate_cash_amount":"361","candidate_known_at":"20230307",
    }]).to_csv(refined,index=False)
    decisions=tmp_path/"decisions.csv"
    pd.DataFrame([
        {"code":"005930","known_at":"20221215","report_nm":"현금ㆍ현물배당 결정",
         "rcept_no":"1","verification_source":"OPENDART_DISCLOSURE_LIST"},
        {"code":"005930","known_at":"20230201","report_nm":"배당기준일 결정",
         "rcept_no":"2","verification_source":"OPENDART_DISCLOSURE_LIST"},
    ]).to_csv(decisions,index=False)
    result=build_stock_dividend_exdate_resolution_queue_v321(
        refined_amount_candidates_csv=str(refined),
        dividend_decisions_csv=str(decisions),
        output_csv=str(tmp_path/"out.csv"),
    )
    assert result["status_counts"]["AMBIGUOUS_DECISION_DISCLOSURES:2"]==1


def test_dividend_cli_namespace_contains_phase512_functions():
    m=importlib.import_module("src.cli.dividend_commands")
    for name in [
        "rank_and_probe_kodex_endpoints_v321",
        "acquire_stock_dividend_decision_disclosures_v321",
        "build_stock_dividend_exdate_resolution_queue_v321",
    ]:
        assert hasattr(m,name), name
