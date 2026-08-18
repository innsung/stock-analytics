import json
import pandas as pd

from src.ml.phase579_explicit_no_dividend_resolution_v321 import resolve_explicit_no_dividend_v321


def test_requires_both_per_share_and_total_explicitly_empty(tmp_path):
    pd.DataFrame([{"queue_event_id":"q","code":"1","residual_status":"NO_DIRECT_DIVIDEND_DECISION"}]).to_csv(tmp_path/"r.csv",index=False)
    raw=json.dumps({"rcept_no":"20250301000001"})
    pd.DataFrame([{"code":"1","business_year":"2024","se":"주당 현금배당금(원)","thstrm":"-","raw_json":raw},
                  {"code":"1","business_year":"2024","se":"현금배당금총액(백만원)","thstrm":"-","raw_json":raw}]).to_csv(tmp_path/"f.csv",index=False)
    result=resolve_explicit_no_dividend_v321(residual_csv=str(tmp_path/"r.csv"),dividend_facts_csv=str(tmp_path/"f.csv"),
        evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"))
    assert result["not_applicable_evidence_rows"] == 1
    assert pd.read_csv(tmp_path/"e.csv").loc[0,"queue_event_id"] == "q"


def test_nonzero_amount_is_not_not_applicable(tmp_path):
    pd.DataFrame([{"queue_event_id":"q","code":"1","residual_status":"NO_DIRECT_DIVIDEND_DECISION"}]).to_csv(tmp_path/"r.csv",index=False)
    raw=json.dumps({"rcept_no":"x"})
    pd.DataFrame([{"code":"1","business_year":"2024","se":"주당 현금배당금(원)","thstrm":"100","raw_json":raw},
                  {"code":"1","business_year":"2024","se":"현금배당금총액(백만원)","thstrm":"10","raw_json":raw}]).to_csv(tmp_path/"f.csv",index=False)
    result=resolve_explicit_no_dividend_v321(residual_csv=str(tmp_path/"r.csv"),dividend_facts_csv=str(tmp_path/"f.csv"),
        evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"))
    assert result["not_applicable_evidence_rows"] == 0
