import pandas as pd
import pytest

from database.database import connect
from src.ml.diagnostics_v32 import (
    _candidates, _read_corporate_actions, run_ml_diagnostics_v32,
)
from tests.test_ml_diagnostics import _seed


def test_v32_nested_selection_champion_and_safety_reports(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn, periods=420)
    prefix = tmp_path / "v32"
    summary = run_ml_diagnostics_v32(
        conn, validation_days=40, test_days=40, min_train_days=240,
        fold_days=40, output_prefix=str(prefix))

    assert summary["version"] == "3.2"
    assert summary["verdict"] == "RESEARCH_ONLY"
    assert summary["candidate_count"] == 5
    assert summary["champion_strategy"] == "v31_champion"
    assert summary["embargo_days"] == 20
    assert summary["criteria"]["nested_purged_selection_completed"] is True
    assert summary["criteria"]["nested_selection_leakage_free"] is True
    assert summary["criteria"]["validation_untouched_during_selection"] is True
    assert summary["criteria"]["point_in_time_universe_verified"] is False
    assert summary["criteria"]["total_return_history_verified"] is False
    assert summary["criteria"]["corporate_action_input_verified"] is False
    assert summary["safety"] == "RESEARCH_AND_SHADOW_ONLY_NO_LIVE_ORDERS"
    assert summary["fallback_policy"]["selection_failure"] == "KEEP_V31_CHAMPION"

    nested = pd.read_csv(tmp_path / "v32_nested_model_selection.csv")
    assert set(nested["strategy_name"]) == {c.strategy_name for c in _candidates()}
    audit = pd.read_csv(tmp_path / "v32_purge_embargo_audit.csv")
    assert audit["purge_passed"].all()
    assert (audit["embargo_days"] >= 20).all()
    assert audit["test_end"].astype(str).max() < summary["validation_period"][0]
    comparison = pd.read_csv(tmp_path / "v32_champion_challenger.csv")
    assert "validation_v31_champion" in set(comparison["split"])
    holdings = pd.read_csv(tmp_path / "v32_holding_contributions.csv", dtype={"code": str})
    assert holdings["entry_close"].notna().all()
    for suffix in (
        "_candidate_manifest.csv", "_dual_benchmark_portfolios.csv", "_portfolio_periods.csv",
        "_portfolio_transitions.csv", "_concentration.csv", "_portfolio_risk.csv",
        "_validation_ic.csv", "_published_test_ic.csv", "_universe_audit.csv",
        "_total_return_audit.csv", "_financial_pit_audit.csv",
        "_corporate_action_audit.csv", "_fallback_policy.json", "_verdict.json",
    ):
        assert (tmp_path / f"v32{suffix}").exists()
    conn.close()


def test_v32_corporate_action_schema_is_strict(tmp_path):
    valid = tmp_path / "actions.csv"
    valid.write_text(
        "code,effective_date,action_type,adjustment_factor,cash_amount,known_at,source\n"
        "005930,20260115,CASH_DIVIDEND,1,361,20251220,test-fixture\n",
        encoding="utf-8")
    frame, verified, status = _read_corporate_actions(str(valid))
    assert verified is True
    assert status == "VERIFIED_CORPORATE_ACTION_INPUT"
    assert frame["row_valid"].all()

    invalid = tmp_path / "invalid-actions.csv"
    invalid.write_text(
        "code,effective_date,action_type,adjustment_factor,cash_amount,known_at,source\n"
        "005930,20260115,CASH_DIVIDEND,1,361,20260116,test-fixture\n",
        encoding="utf-8")
    _, verified, status = _read_corporate_actions(str(invalid))
    assert verified is False
    assert status == "INVALID_CORPORATE_ACTION_INPUT"


def test_v32_rejects_weak_embargo_and_risk_caps(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn)
    with pytest.raises(ValueError, match="embargo-days"):
        run_ml_diagnostics_v32(
            conn, validation_days=40, test_days=40, min_train_days=240,
            fold_days=40, embargo_days=10, output_prefix=str(tmp_path / "bad"))
    with pytest.raises(ValueError, match="stock-cap"):
        run_ml_diagnostics_v32(
            conn, validation_days=40, test_days=40, min_train_days=240,
            fold_days=40, stock_cap=.20, output_prefix=str(tmp_path / "bad2"))
    conn.close()
