import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.ml.benchmark_etf_distribution_v321 import (
    prepare_benchmark_etf_distribution_template_v321,
    validate_benchmark_etf_distributions_v321,
    inject_benchmark_etf_events_v321,
    summarize_stock_dividend_resolution_v321,
)


def test_prepare_empty_template_does_not_infer_events(tmp_path):
    result = prepare_benchmark_etf_distribution_template_v321(
        output_csv=str(tmp_path/"etf.csv")
    )
    f = pd.read_csv(tmp_path/"etf.csv")
    assert len(f) == 0
    assert "ex_date" in f.columns
    assert Path(result["manifest"]).exists()


def test_validate_official_etf_distribution_strict(tmp_path):
    src = tmp_path/"official.csv"
    pd.DataFrame([{
        "code":"069500","record_date":"20260430","ex_date":"20260429",
        "pay_date":"20260506","announced_at":"20260420","cash_amount":"446",
        "currency":"KRW","issuer":"Samsung Asset Management",
        "verification_source":"SAMSUNG_KODEX_OFFICIAL",
        "verification_reference":"dist-2026-04",
        "source_url":"https://m.samsungfund.com/etf/product/view.do?id=2ETF01",
        "note":"",
    }]).to_csv(src,index=False)
    result = validate_benchmark_etf_distributions_v321(
        official_csv=str(src),
        strict_evidence_csv=str(tmp_path/"strict.csv"),
        audit_csv=str(tmp_path/"audit.csv"),
    )
    assert result["strict_rows"] == 1
    f = pd.read_csv(tmp_path/"strict.csv", dtype=str)
    assert f.iloc[0]["action_type"] == "ETF_DISTRIBUTION"
    assert f.iloc[0]["effective_date"] == "20260429"


def test_validate_rejects_late_announcement(tmp_path):
    src = tmp_path/"bad.csv"
    pd.DataFrame([{
        "code":"069500","record_date":"20260430","ex_date":"20260429",
        "pay_date":"20260506","announced_at":"20260501","cash_amount":"446",
        "currency":"KRW","issuer":"Samsung Asset Management",
        "verification_source":"SAMSUNG_KODEX_OFFICIAL",
        "verification_reference":"dist",
        "source_url":"https://m.samsungfund.com/etf/product/view.do?id=2ETF01",
    }]).to_csv(src,index=False)
    with pytest.raises(ValueError, match="invalid_rows=1"):
        validate_benchmark_etf_distributions_v321(
            official_csv=str(src),
            strict_evidence_csv=str(tmp_path/"strict.csv"),
            audit_csv=str(tmp_path/"audit.csv"),
        )


def test_inject_benchmark_events_preserves_stock_rows(tmp_path):
    strict = tmp_path/"strict.csv"
    pd.DataFrame([{
        "queue_event_id":"etf_abc","code":"069500",
        "event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20260430","effective_date":"20260429",
        "known_at":"20260420","action_type":"ETF_DISTRIBUTION",
        "adjustment_factor":"1","cash_amount":"446",
        "verification_source":"OFFICIAL","verification_reference":"ref",
        "resolution_note":"STRICT_OFFICIAL_BENCHMARK_ETF_DISTRIBUTION",
    }]).to_csv(strict,index=False)
    verification = tmp_path/"verification.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307","source_description":"annual",
        "resolution_status":"UNRESOLVED","effective_date":"","known_at":"",
        "action_type":"","adjustment_factor":"","cash_amount":"",
        "verification_source":"","verification_reference":"","resolution_note":"",
    }]).to_csv(verification,index=False)
    registry = tmp_path/"registry.csv"
    pd.DataFrame([{
        "code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307","source_description":"annual",
        "candidate_cash_amount":"","candidate_adjustment_factor":"1",
        "candidate_effective_date":"","candidate_known_at":"",
        "action_type":"","verification_source":"","verification_status":"",
        "queue_event_id":"q1",
    }]).to_csv(registry,index=False)

    result = inject_benchmark_etf_events_v321(
        strict_evidence_csv=str(strict),
        verification_csv=str(verification),
        queue_registry_csv=str(registry),
        output_verification_csv=str(tmp_path/"v2.csv"),
        output_registry_csv=str(tmp_path/"r2.csv"),
    )
    assert result["etf_rows_added"] == 1
    v = pd.read_csv(tmp_path/"v2.csv", dtype=str)
    assert set(v["code"]) == {"005930","069500"}
    assert v[v["code"]=="069500"].iloc[0]["resolution_status"] == "VERIFIED"


def test_stock_dividend_summary(tmp_path):
    cand = tmp_path/"cand.csv"
    pd.DataFrame([{"queue_event_id":"q1","candidate_cash_amount":"100"}]).to_csv(cand,index=False)
    audit = tmp_path/"audit.csv"
    pd.DataFrame([
        {"queue_event_id":"q1","status":"UNIQUE_AMOUNT_CANDIDATE"},
        {"queue_event_id":"q2","status":"NO_AMOUNT_CANDIDATE"},
    ]).to_csv(audit,index=False)
    result = summarize_stock_dividend_resolution_v321(
        amount_candidates_csv=str(cand), amount_audit_csv=str(audit),
        output_json=str(tmp_path/"summary.json"),
    )
    assert result["cash_amount_candidate_rows"] == 1
    assert result["status_counts"]["NO_AMOUNT_CANDIDATE"] == 1


def test_dividend_cli_namespace_contains_phase59_functions():
    m = importlib.import_module("src.cli.dividend_commands")
    for name in [
        "prepare_benchmark_etf_distribution_template_v321",
        "validate_benchmark_etf_distributions_v321",
        "inject_benchmark_etf_events_v321",
        "summarize_stock_dividend_resolution_v321",
    ]:
        assert hasattr(m, name), name
