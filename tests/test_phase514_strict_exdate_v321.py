
import importlib
import sqlite3
from pathlib import Path

import pandas as pd

from src.ml.phase514_strict_exdate_v321 import (
    build_explicit_stock_exdate_strict_evidence_v321,
    build_record_date_calendar_candidates_v321,
    parse_kodex_distribution_tables_v321,
    export_benchmark_calendar_from_db_v321,
)


def test_only_explicit_exdate_promotes(tmp_path):
    src=tmp_path/"resolution.csv"
    pd.DataFrame([
        {
            "queue_event_id":"q1","code":"005930","source_reference_date":"20230307",
            "candidate_cash_amount":"361","official_date_match_status":"UNIQUE_OFFICIAL_DATE_CANDIDATE",
            "official_date_role":"EX_DATE","official_date_candidate":"20221228",
            "official_date_known_at":"20221215","official_date_source":"OPENDART_DOCUMENT_ORIGINAL",
            "official_date_reference":"A",
        },
        {
            "queue_event_id":"q2","code":"000660","source_reference_date":"20230307",
            "candidate_cash_amount":"1200","official_date_match_status":"UNIQUE_OFFICIAL_DATE_CANDIDATE",
            "official_date_role":"RECORD_DATE","official_date_candidate":"20221231",
            "official_date_known_at":"20221215","official_date_source":"OPENDART_DOCUMENT_ORIGINAL",
            "official_date_reference":"B",
        },
    ]).to_csv(src,index=False)
    result=build_explicit_stock_exdate_strict_evidence_v321(
        stock_dividend_date_resolution_csv=str(src),
        output_csv=str(tmp_path/"strict.csv"),audit_csv=str(tmp_path/"audit.csv")
    )
    assert result["strict_rows"]==1
    out=pd.read_csv(tmp_path/"strict.csv",dtype=str)
    assert out.iloc[0]["queue_event_id"]=="q1"
    assert out.iloc[0]["effective_date"]=="20221228"


def test_record_date_calendar_is_context_only(tmp_path):
    src=tmp_path/"resolution.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","official_date_role":"RECORD_DATE",
        "official_date_candidate":"20221231",
    }]).to_csv(src,index=False)
    prices=tmp_path/"prices.csv"
    pd.DataFrame([
        {"date":"20221227","close":"100"},
        {"date":"20221228","close":"99"},
        {"date":"20221229","close":"98"},
        {"date":"20230102","close":"97"},
    ]).to_csv(prices,index=False)
    result=build_record_date_calendar_candidates_v321(
        stock_dividend_date_resolution_csv=str(src),
        benchmark_prices_csv=str(prices),output_csv=str(tmp_path/"out.csv")
    )
    assert result["rows"]==1
    out=pd.read_csv(tmp_path/"out.csv",dtype=str)
    assert out.iloc[0]["prior_trading_day_1"]=="20221229"
    assert out.iloc[0]["promotion_status"]=="CALENDAR_CONTEXT_ONLY_NOT_EXDATE_EVIDENCE"


def test_parse_kodex_date_amount_pair(tmp_path):
    bodies=tmp_path/"bodies"; bodies.mkdir()
    (bodies/"x.html").write_text(
        "<table><tr><td>분배금 지급현황</td><td>2026.04.29</td><td>446원</td></tr></table>",
        encoding="utf-8"
    )
    result=parse_kodex_distribution_tables_v321(
        bodies_dir=str(bodies),output_csv=str(tmp_path/"out.csv"),audit_csv=str(tmp_path/"audit.csv")
    )
    assert result["candidate_pairs"]>=1
    out=pd.read_csv(tmp_path/"out.csv")
    assert "20260429" in out["candidate_date"].astype(str).tolist()
    assert 446.0 in out["cash_amount"].astype(float).tolist()


def test_export_benchmark_calendar_from_db(tmp_path):
    conn=sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE stock_prices (code TEXT, date TEXT, close REAL)")
    conn.executemany(
        "INSERT INTO stock_prices(code,date,close) VALUES(?,?,?)",
        [("069500","20260708",100.0),("069500","20260709",101.0),("069500","20260710",102.0)]
    )
    result=export_benchmark_calendar_from_db_v321(
        conn,code="069500",output_csv=str(tmp_path/"calendar.csv")
    )
    assert result["rows"]==2
    assert result["last_date"]=="20260709"


def test_main_namespace_contains_phase514_functions():
    m=importlib.import_module("src.main")
    for name in [
        "build_explicit_stock_exdate_strict_evidence_v321",
        "build_record_date_calendar_candidates_v321",
        "parse_kodex_distribution_tables_v321",
        "export_benchmark_calendar_from_db_v321",
    ]:
        assert hasattr(m,name),name
