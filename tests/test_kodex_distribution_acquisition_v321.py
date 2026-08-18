import importlib
from pathlib import Path
import pandas as pd

from src.ml.kodex_distribution_acquisition_v321 import (
    build_stock_dividend_ambiguity_report_v321,
)

def test_stock_dividend_ambiguity_report(tmp_path):
    audit=tmp_path/"audit.csv"
    pd.DataFrame([
        {"queue_event_id":"q1","code":"005930","source_reference_date":"20230307","status":"UNIQUE_AMOUNT_CANDIDATE"},
        {"queue_event_id":"q2","code":"000660","source_reference_date":"20230310","status":"AMBIGUOUS_AMOUNT_CANDIDATES:2"},
        {"queue_event_id":"q3","code":"035420","source_reference_date":"20230315","status":"NO_AMOUNT_CANDIDATE"},
    ]).to_csv(audit,index=False)
    cand=tmp_path/"cand.csv"
    pd.DataFrame([{"queue_event_id":"q1","candidate_cash_amount":"361"}]).to_csv(cand,index=False)
    result=build_stock_dividend_ambiguity_report_v321(
        amount_audit_csv=str(audit),
        amount_candidates_csv=str(cand),
        output_csv=str(tmp_path/"out.csv"),
    )
    assert result["rows"]==3
    assert result["unique"]==1
    assert result["ambiguous"]==1
    assert result["missing"]==1

def test_main_namespace_contains_phase510_functions():
    m=importlib.import_module("src.main")
    assert hasattr(m,"acquire_kodex_distribution_candidates_v321")
    assert hasattr(m,"build_stock_dividend_ambiguity_report_v321")
