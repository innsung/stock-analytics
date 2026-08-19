
import importlib
from pathlib import Path

import pandas as pd

from src.ml.phase513_parsers_v321 import (
    merge_dividend_amount_and_record_candidates_v321,
)


def test_merge_unique_record_date_candidate(tmp_path):
    q=tmp_path/"q.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","source_reference_date":"20230307",
        "candidate_cash_amount":"361","decision_rcept_no":"202212150001",
    }]).to_csv(q,index=False)
    r=tmp_path/"r.csv"
    pd.DataFrame([{
        "code":"005930","rcept_no":"202212150001","date_role":"RECORD_DATE",
        "candidate_date":"20221231","known_at":"20221215",
        "verification_source":"OPENDART_DOCUMENT_ORIGINAL",
        "verification_reference":"202212150001",
    }]).to_csv(r,index=False)
    result=merge_dividend_amount_and_record_candidates_v321(
        exdate_queue_csv=str(q),
        dart_record_candidates_csv=str(r),
        output_csv=str(tmp_path/"out.csv"),
    )
    assert result["rows"]==1
    out=pd.read_csv(tmp_path/"out.csv",dtype=str).fillna("")
    assert out.iloc[0]["official_date_role"]=="RECORD_DATE"
    assert out.iloc[0]["official_date_candidate"]=="20221231"
    assert out.iloc[0]["effective_date"]==""
    assert out.iloc[0]["next_required_evidence"]=="KRX_TRADING_CALENDAR_RECORD_TO_EXDATE_MAPPING"


def test_merge_exact_rcept_preferred(tmp_path):
    q=tmp_path/"q.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","source_reference_date":"20230307",
        "candidate_cash_amount":"361","decision_rcept_no":"A",
    }]).to_csv(q,index=False)
    r=tmp_path/"r.csv"
    pd.DataFrame([
        {"code":"005930","rcept_no":"A","date_role":"EX_DATE","candidate_date":"20221228",
         "known_at":"20221215","verification_source":"DART","verification_reference":"A"},
        {"code":"005930","rcept_no":"B","date_role":"RECORD_DATE","candidate_date":"20221231",
         "known_at":"20221216","verification_source":"DART","verification_reference":"B"},
    ]).to_csv(r,index=False)
    result=merge_dividend_amount_and_record_candidates_v321(
        exdate_queue_csv=str(q),
        dart_record_candidates_csv=str(r),
        output_csv=str(tmp_path/"out.csv"),
    )
    out=pd.read_csv(tmp_path/"out.csv",dtype=str).fillna("")
    assert out.iloc[0]["official_date_role"]=="EX_DATE"
    assert out.iloc[0]["next_required_evidence"]=="EX_DATE_CONFIRMED"


class FakeDart:
    def document_texts(self, rcept_no):
        return [{
            "name":"doc.xml",
            "text":"<TABLE><TR><TD>배당기준일</TD><TD>2022년 12월 31일</TD></TR></TABLE>",
        }]


def test_extract_dart_record_date_unique(tmp_path):
    from src.ml.phase513_parsers_v321 import extract_dart_dividend_record_dates_v321
    d=tmp_path/"d.csv"
    pd.DataFrame([{
        "code":"005930","known_at":"20221215","report_nm":"현금ㆍ현물배당 결정",
        "rcept_no":"A","verification_source":"OPENDART_DISCLOSURE_LIST",
    }]).to_csv(d,index=False)
    result=extract_dart_dividend_record_dates_v321(
        FakeDart(),
        decision_disclosures_csv=str(d),
        output_csv=str(tmp_path/"out.csv"),
        audit_csv=str(tmp_path/"audit.csv"),
        sleep_seconds=0,
    )
    assert result["date_candidates"]==1
    out=pd.read_csv(tmp_path/"out.csv",dtype=str)
    assert out.iloc[0]["date_role"]=="RECORD_DATE"
    assert out.iloc[0]["candidate_date"]=="20221231"


def test_dividend_cli_namespace_contains_phase513_functions():
    m=importlib.import_module("src.cli.dividend_commands")
    for name in [
        "inspect_kodex_probe_responses_v321",
        "extract_dart_dividend_record_dates_v321",
        "merge_dividend_amount_and_record_candidates_v321",
    ]:
        assert hasattr(m,name), name
