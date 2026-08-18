import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.ml.cash_distribution_v321 import (
    build_stock_cash_amount_candidates_v321,
    prepare_official_cash_event_template_v321,
    validate_official_cash_events_v321,
    compare_cash_amount_candidates_v321,
)


def _verification(path: Path):
    pd.DataFrame([
        {
            "queue_event_id":"q_stock","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
            "source_reference_date":"20230307","source_description":"annual dividend",
            "resolution_status":"UNRESOLVED","effective_date":"","known_at":"","action_type":"",
            "adjustment_factor":"","cash_amount":"","verification_source":"",
            "verification_reference":"","resolution_note":"",
        },
        {
            "queue_event_id":"q_etf","code":"069500","event_family":"DIVIDEND_OR_DISTRIBUTION",
            "source_reference_date":"20230501","source_description":"ETF distribution",
            "resolution_status":"UNRESOLVED","effective_date":"","known_at":"","action_type":"",
            "adjustment_factor":"","cash_amount":"","verification_source":"",
            "verification_reference":"","resolution_note":"",
        },
    ]).to_csv(path,index=False)


def test_build_stock_cash_amount_candidate_from_dart(tmp_path):
    facts=tmp_path/"facts.csv"
    pd.DataFrame([
        {"code":"005930","business_year":"2022","disclosed_at":"20230307",
         "se":"주당 현금배당금(원)","stock_knd":"보통주","thstrm":"361",
         "source":"OPENDART_ALOT_MATTER"},
        {"code":"005930","business_year":"2022","disclosed_at":"20230307",
         "se":"현금배당수익률(%)","stock_knd":"보통주","thstrm":"2.1",
         "source":"OPENDART_ALOT_MATTER"},
    ]).to_csv(facts,index=False)
    v=tmp_path/"verification.csv"; _verification(v)
    result=build_stock_cash_amount_candidates_v321(
        dividend_facts_csv=str(facts),verification_csv=str(v),
        output_csv=str(tmp_path/"out.csv"),audit_csv=str(tmp_path/"audit.csv"),
    )
    assert result["queue_rows"] == 1
    assert result["amount_candidate_rows"] == 1
    out=pd.read_csv(tmp_path/"out.csv")
    assert float(out.iloc[0]["candidate_cash_amount"]) == 361
    assert pd.isna(out.iloc[0]["effective_date"]) or out.iloc[0]["effective_date"] == ""


def test_prepare_cash_template_separates_etf(tmp_path):
    v=tmp_path/"verification.csv"; _verification(v)
    result=prepare_official_cash_event_template_v321(
        verification_csv=str(v),output_csv=str(tmp_path/"cash.csv")
    )
    assert result["stock_rows"] == 1
    assert result["etf_rows"] == 1
    f=pd.read_csv(tmp_path/"cash.csv",dtype=str)
    assert f.loc[f["code"]=="069500","action_type"].iloc[0] == "ETF_DISTRIBUTION"


def test_validate_strict_cash_events(tmp_path):
    p=tmp_path/"cash.csv"
    pd.DataFrame([
        {"queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
         "source_reference_date":"20230307","effective_date":"20221228","known_at":"20221215",
         "action_type":"CASH_DIVIDEND","adjustment_factor":"1","cash_amount":"361",
         "verification_source":"OFFICIAL_EXDATE_SOURCE","verification_reference":"r1","resolution_note":""},
        {"queue_event_id":"q2","code":"069500","event_family":"DIVIDEND_OR_DISTRIBUTION",
         "source_reference_date":"20230501","effective_date":"20230427","known_at":"20230420",
         "action_type":"ETF_DISTRIBUTION","adjustment_factor":"1","cash_amount":"100",
         "verification_source":"OFFICIAL_ETF_SOURCE","verification_reference":"r2","resolution_note":""},
    ]).to_csv(p,index=False)
    result=validate_official_cash_events_v321(
        official_cash_events_csv=str(p),
        output_csv=str(tmp_path/"strict.csv"),
        audit_csv=str(tmp_path/"audit.csv"),
    )
    assert result["strict_cash_evidence_rows"] == 2
    assert result["stock_dividend_rows"] == 1
    assert result["etf_distribution_rows"] == 1


def test_validate_rejects_missing_exdate_and_wrong_etf_type(tmp_path):
    p=tmp_path/"bad.csv"
    pd.DataFrame([{
        "queue_event_id":"q","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307","effective_date":"","known_at":"20221215",
        "action_type":"ETF_DISTRIBUTION","adjustment_factor":"1","cash_amount":"100",
        "verification_source":"OFFICIAL","verification_reference":"x",
    }]).to_csv(p,index=False)
    with pytest.raises(ValueError,match="invalid_rows=1"):
        validate_official_cash_events_v321(
            official_cash_events_csv=str(p),
            output_csv=str(tmp_path/"strict.csv"),audit_csv=str(tmp_path/"audit.csv")
        )


def test_cash_amount_crosscheck_detects_match(tmp_path):
    strict=tmp_path/"strict.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307","effective_date":"20221228","known_at":"20221215",
        "action_type":"CASH_DIVIDEND","adjustment_factor":"1","cash_amount":"361",
        "verification_source":"OFFICIAL","verification_reference":"x","resolution_note":""
    }]).to_csv(strict,index=False)
    cand=tmp_path/"cand.csv"
    pd.DataFrame([{"queue_event_id":"q1","candidate_cash_amount":"361"}]).to_csv(cand,index=False)
    result=compare_cash_amount_candidates_v321(
        strict_cash_evidence_csv=str(strict),
        amount_candidates_csv=str(cand),
        output_csv=str(tmp_path/"audit.csv"),
    )
    assert result["matches"] == 1
    assert result["mismatches"] == 0


def test_main_namespace_contains_phase58_functions():
    m=importlib.import_module("src.main")
    for name in [
        "build_stock_cash_amount_candidates_v321",
        "prepare_official_cash_event_template_v321",
        "validate_official_cash_events_v321",
        "compare_cash_amount_candidates_v321",
    ]:
        assert hasattr(m,name), name
