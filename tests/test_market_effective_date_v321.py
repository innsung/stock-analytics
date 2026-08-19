import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.ml.market_effective_date_v321 import (
    detect_adjustment_breakpoints_v321,
    build_market_adjustment_evidence_v321,
    merge_strict_evidence_v321,
)


class FakeProvider:
    def ohlcv(self, start, end, code, adjusted):
        dates = pd.to_datetime(["2020-06-26","2020-06-29","2020-06-30","2020-07-01"])
        if adjusted:
            close = [50, 50, 50, 50]
        else:
            close = [100, 100, 50, 50]
        return pd.DataFrame({"종가": close}, index=dates)


def test_detect_breakpoint_from_adjusted_raw_ratio():
    bp = detect_adjustment_breakpoints_v321(
        FakeProvider(), code="005930", center_date="20200630",
        window_days=10, ratio_tolerance=.001,
    )
    assert len(bp) == 1
    assert bp.iloc[0]["date"] == "20200630"
    assert float(bp.iloc[0]["ratio_change"]) == 2.0


def test_build_market_evidence_only_for_safe_factor_actions(tmp_path):
    candidates = tmp_path/"candidates.csv"
    pd.DataFrame([
        {
            "code":"005930","official_known_at":"20200601","official_event_date":"20200630",
            "action_type_hint":"BONUS","verification_source":"OPENDART_fricDecsn",
            "verification_reference":"abc",
        },
        {
            "code":"005930","official_known_at":"20200601","official_event_date":"20200630",
            "action_type_hint":"MERGER","verification_source":"OPENDART_cmpMgDecsn",
            "verification_reference":"def",
        },
    ]).to_csv(candidates,index=False)
    result = build_market_adjustment_evidence_v321(
        FakeProvider(), official_candidates_csv=str(candidates),
        output_csv=str(tmp_path/"evidence.csv"), audit_csv=str(tmp_path/"audit.csv"),
        window_days=10, max_match_distance_days=5, ratio_tolerance=.001,
    )
    assert result["strict_market_evidence_rows"] == 1
    ev = pd.read_csv(tmp_path/"evidence.csv", dtype=str)
    assert ev.iloc[0]["action_type"] == "BONUS"
    assert float(ev.iloc[0]["adjustment_factor"]) == 2.0
    audit = pd.read_csv(tmp_path/"audit.csv", dtype=str)
    merger = audit[audit["action_type_hint"]=="MERGER"].iloc[0]
    assert merger["status"] == "UNRESOLVED"


def test_cash_dividend_never_autoresolved(tmp_path):
    candidates=tmp_path/"c.csv"
    pd.DataFrame([{
        "code":"005930","official_known_at":"20200601","official_event_date":"20200630",
        "action_type_hint":"CASH_DIVIDEND","verification_source":"OFFICIAL",
        "verification_reference":"x",
    }]).to_csv(candidates,index=False)
    result=build_market_adjustment_evidence_v321(
        FakeProvider(), official_candidates_csv=str(candidates),
        output_csv=str(tmp_path/"e.csv"), audit_csv=str(tmp_path/"a.csv"),
    )
    assert result["strict_market_evidence_rows"] == 0


def test_merge_strict_evidence_rejects_conflicts(tmp_path):
    a=tmp_path/"a.csv"; b=tmp_path/"b.csv"
    base={
        "queue_event_id":"","code":"005930","event_family":"CORPORATE_ACTION",
        "source_reference_date":"20200630","effective_date":"20200630","known_at":"20200601",
        "action_type":"BONUS","adjustment_factor":"2","cash_amount":"0",
        "verification_source":"KRX_A","verification_reference":"a","resolution_note":"x",
    }
    pd.DataFrame([base]).to_csv(a,index=False)
    other=base|{"adjustment_factor":"1.5","verification_source":"KRX_B","verification_reference":"b"}
    pd.DataFrame([other]).to_csv(b,index=False)
    with pytest.raises(ValueError, match="충돌"):
        merge_strict_evidence_v321(evidence_csvs=[str(a),str(b)], output_csv=str(tmp_path/"out.csv"))


def test_event_cli_namespace_contains_phase57_functions():
    m=importlib.import_module("src.cli.event_commands")
    assert hasattr(m,"build_market_adjustment_evidence_v321")
    assert hasattr(m,"merge_strict_evidence_v321")
