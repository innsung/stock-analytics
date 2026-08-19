
import importlib
from pathlib import Path
import pandas as pd

from src.ml.phase515_market_exdate_v321 import (
    build_market_exdate_verification_queue_v321,
    validate_official_market_exdates_v321,
    summarize_kodex_high_signal_bodies_v321,
)


def test_build_market_exdate_queue_prioritizes_record_dates(tmp_path):
    res=tmp_path/"res.csv"
    pd.DataFrame([
        {
            "queue_event_id":"q1","code":"005930","candidate_cash_amount":"361",
            "official_date_match_status":"UNIQUE_OFFICIAL_DATE_CANDIDATE",
            "official_date_role":"RECORD_DATE","official_date_candidate":"20221231",
            "official_date_known_at":"20221215","official_date_source":"DART",
            "official_date_reference":"A",
        },
        {
            "queue_event_id":"q2","code":"000660","candidate_cash_amount":"1200",
            "official_date_match_status":"NO_OFFICIAL_DATE_CANDIDATE",
            "official_date_role":"","official_date_candidate":"",
            "official_date_known_at":"","official_date_source":"",
            "official_date_reference":"",
        },
    ]).to_csv(res,index=False)
    cal=tmp_path/"cal.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","record_date":"20221231",
        "prior_trading_day_1":"20221229","prior_trading_day_2":"20221228",
        "next_or_same_trading_day":"20230102",
    }]).to_csv(cal,index=False)
    result=build_market_exdate_verification_queue_v321(
        stock_dividend_date_resolution_csv=str(res),
        record_date_calendar_candidates_csv=str(cal),
        output_csv=str(tmp_path/"out.csv"),
    )
    assert result["rows"]==2
    out=pd.read_csv(tmp_path/"out.csv",dtype=str).fillna("")
    q1=out[out["queue_event_id"]=="q1"].iloc[0]
    assert q1["priority"]=="P1_RECORD_DATE_READY_FOR_MARKET_VERIFICATION"
    assert q1["market_ex_date"]==""


def test_validate_official_market_exdate_strict(tmp_path):
    v=tmp_path/"v.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","candidate_cash_amount":"361",
        "record_date":"20221231","known_at":"20221215","market_ex_date":"20221228",
        "market_source":"KRX_OFFICIAL","market_reference":"ref1",
        "market_source_url":"https://example.com","market_note":""
    }]).to_csv(v,index=False)
    result=validate_official_market_exdates_v321(
        verification_csv=str(v),
        strict_evidence_csv=str(tmp_path/"strict.csv"),
        audit_csv=str(tmp_path/"audit.csv"),
    )
    assert result["strict_rows"]==1
    out=pd.read_csv(tmp_path/"strict.csv",dtype=str)
    assert out.iloc[0]["effective_date"]=="20221228"


def test_validate_rejects_blank_source(tmp_path):
    v=tmp_path/"v.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","candidate_cash_amount":"361",
        "record_date":"20221231","known_at":"20221215","market_ex_date":"20221228",
        "market_source":"","market_reference":"ref1",
        "market_source_url":"","market_note":""
    }]).to_csv(v,index=False)
    result=validate_official_market_exdates_v321(
        verification_csv=str(v),
        strict_evidence_csv=str(tmp_path/"strict.csv"),
        audit_csv=str(tmp_path/"audit.csv"),
    )
    assert result["strict_rows"]==0
    assert result["invalid_rows"]==1


def test_kodex_summary(tmp_path):
    audit=tmp_path/"audit.csv"
    pd.DataFrame([{
        "status":"OK","content_type":"text/html","date_fields":"0","amount_fields":"0"
    }]).to_csv(audit,index=False)
    fields=tmp_path/"fields.csv"
    pd.DataFrame([{"url":"x","path":"HTML_CONTEXT"}]).to_csv(fields,index=False)
    result=summarize_kodex_high_signal_bodies_v321(
        response_audit_csv=str(audit),
        field_candidates_csv=str(fields),
        output_json=str(tmp_path/"summary.json"),
    )
    assert result["responses"]==1
    assert result["responses_with_date_fields"]==0


def test_dividend_cli_namespace_contains_phase515_functions():
    m=importlib.import_module("src.cli.dividend_commands")
    for name in [
        "build_market_exdate_verification_queue_v321",
        "validate_official_market_exdates_v321",
        "summarize_kodex_high_signal_bodies_v321",
    ]:
        assert hasattr(m,name),name
