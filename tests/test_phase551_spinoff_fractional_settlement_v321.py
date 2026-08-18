import json
import pandas as pd
import pytest

from src.ml.phase551_spinoff_fractional_settlement_v321 import audit_spinoff_fractional_settlement_v321


def test_extracts_explicit_rule_and_values_fractional_cash(tmp_path):
    official, audit = tmp_path / "o.csv", tmp_path / "a.csv"
    rule, scenarios = tmp_path / "rule.csv", tmp_path / "scenarios.csv"
    text = "1주 미만 단주는 재상장 초일의 종가로 환산하여 현금으로 지급하며 자기주식으로 취득"
    pd.DataFrame([{"rcept_no": "r", "raw_json": json.dumps({"abcr_shstkcnt_rt_at_rs": text})}]).to_csv(official, index=False)
    pd.DataFrame([{"rcept_no": "r", "parent_code": "p", "child_code": "c",
        "distributed_ratio": 0.35, "child_first_close": 400,
        "first_joint_trade_date": "20251124"}]).to_csv(audit, index=False)
    result = audit_spinoff_fractional_settlement_v321(
        official_candidates_csv=str(official), valuation_audit_csv=str(audit),
        rule_output_csv=str(rule), scenario_output_csv=str(scenarios), receipt_no="r",
        scenario_quantities=(1, 10))
    frame = pd.read_csv(scenarios)
    assert result["canonical_total_return_ready"] is False
    assert frame.iloc[0]["fractional_cash_settlement"] == pytest.approx(140)
    assert frame.iloc[1]["whole_distributed_shares"] == 3
    assert frame.iloc[1]["fractional_cash_settlement"] == pytest.approx(200)


def test_rejects_non_explicit_rule(tmp_path):
    official, audit = tmp_path / "o.csv", tmp_path / "a.csv"
    pd.DataFrame([{"rcept_no": "r", "raw_json": "{}"}]).to_csv(official, index=False)
    pd.DataFrame([{"rcept_no": "r"}]).to_csv(audit, index=False)
    with pytest.raises(ValueError, match="explicit fractional-share"):
        audit_spinoff_fractional_settlement_v321(
            official_candidates_csv=str(official), valuation_audit_csv=str(audit),
            rule_output_csv=str(tmp_path / "r.csv"), scenario_output_csv=str(tmp_path / "s.csv"),
            receipt_no="r")
