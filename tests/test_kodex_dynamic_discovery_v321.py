
import importlib
from pathlib import Path
import pandas as pd

from src.ml.kodex_dynamic_discovery_v321 import (
    refine_stock_dividend_candidates_v321,
)


def test_refine_prefers_previous_business_year(tmp_path):
    facts=tmp_path/"facts.csv"
    pd.DataFrame([
        {"code":"005930","business_year":"2022","disclosed_at":"20230307",
         "se":"주당 현금배당금(원)","stock_knd":"보통주","thstrm":"361","source":"OPENDART"},
        {"code":"005930","business_year":"2023","disclosed_at":"20240307",
         "se":"주당 현금배당금(원)","stock_knd":"보통주","thstrm":"400","source":"OPENDART"},
    ]).to_csv(facts,index=False)
    ver=tmp_path/"ver.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307",
    }]).to_csv(ver,index=False)
    result=refine_stock_dividend_candidates_v321(
        dividend_facts_csv=str(facts),verification_csv=str(ver),
        output_csv=str(tmp_path/"out.csv"),audit_csv=str(tmp_path/"audit.csv")
    )
    assert result["candidate_rows"]==1
    out=pd.read_csv(tmp_path/"out.csv")
    assert int(out.iloc[0]["selected_business_year"])==2022
    assert float(out.iloc[0]["candidate_cash_amount"])==361


def test_refine_falls_back_to_reference_year(tmp_path):
    facts=tmp_path/"facts.csv"
    pd.DataFrame([{
        "code":"005930","business_year":"2023","disclosed_at":"20230307",
        "se":"주당 현금배당금(원)","stock_knd":"보통주","thstrm":"400","source":"OPENDART"
    }]).to_csv(facts,index=False)
    ver=tmp_path/"ver.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307",
    }]).to_csv(ver,index=False)
    result=refine_stock_dividend_candidates_v321(
        dividend_facts_csv=str(facts),verification_csv=str(ver),
        output_csv=str(tmp_path/"out.csv"),audit_csv=str(tmp_path/"audit.csv")
    )
    assert "UNIQUE_AMOUNT_CANDIDATE_FALLBACK_YEAR" in result["status_counts"]


def test_refine_keeps_within_year_ambiguity(tmp_path):
    facts=tmp_path/"facts.csv"
    pd.DataFrame([
        {"code":"005930","business_year":"2022","disclosed_at":"20230307",
         "se":"주당 현금배당금(원)","stock_knd":"보통주","thstrm":"361","source":"OPENDART"},
        {"code":"005930","business_year":"2022","disclosed_at":"20230307",
         "se":"주당 현금배당금(원)","stock_knd":"보통주","thstrm":"1444","source":"OPENDART"},
    ]).to_csv(facts,index=False)
    ver=tmp_path/"ver.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307",
    }]).to_csv(ver,index=False)
    result=refine_stock_dividend_candidates_v321(
        dividend_facts_csv=str(facts),verification_csv=str(ver),
        output_csv=str(tmp_path/"out.csv"),audit_csv=str(tmp_path/"audit.csv")
    )
    assert result["candidate_rows"]==0
    assert "AMBIGUOUS_WITHIN_BUSINESS_YEAR:2" in result["status_counts"]


def test_dividend_cli_namespace_contains_phase511_functions():
    m=importlib.import_module("src.cli.dividend_commands")
    assert hasattr(m,"discover_kodex_dynamic_endpoints_v321")
    assert hasattr(m,"refine_stock_dividend_candidates_v321")
