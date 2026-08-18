import subprocess
import sys

import pandas as pd
import pytest

from database.database import connect
from src.ml.diagnostics_v321 import (
    RESEARCH_SEEN_THROUGH,
    _candidates,
    _financial_point_in_time_audit,
    run_ml_diagnostics_v321,
)
from tests.test_ml_diagnostics import _seed


def test_v321_common_overlay_and_reports(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn, periods=420, codes=8)
    prefix = tmp_path / "v321"
    summary = run_ml_diagnostics_v321(
        conn, validation_days=40, test_days=40, min_train_days=240,
        fold_days=40, output_prefix=str(prefix))
    assert summary["version"] == "3.2.1"
    assert summary["research_seen_through"] == RESEARCH_SEEN_THROUGH
    assert summary["criteria"]["common_risk_overlay_applied_to_all_strategies"] is True
    assert summary["risk_limits"]["minimum_stocks"] == 7
    assert summary["risk_limits"]["stock_cap"] <= .15
    assert summary["risk_limits"]["industry_cap"] <= .40
    assert summary["sealed_test_policy"]["retuning_after_20260710"] == "PROHIBITED"

    constraints = pd.read_csv(tmp_path / "v321_hard_constraint_audit.csv")
    assert not constraints[["stock_cap_violation", "industry_cap_violation", "exposure_violation"]].any().any()
    periods = pd.read_csv(tmp_path / "v321_portfolio_periods.csv")
    assert (periods["target_exposure"] <= periods["market_exposure_limit"] + 1e-9).all()
    assert "simultaneous_dual_win" in periods.columns
    portfolios = pd.read_csv(tmp_path / "v321_dual_benchmark_portfolios.csv")
    assert "cumulative_dual_outperformance" in portfolios.columns
    assert "simultaneous_dual_win_rate" in portfolios.columns
    for suffix in ("_fixation_audit.csv", "_outlier_contribution_stress.csv",
                   "_financial_pit_audit.csv", "_hard_constraint_audit.csv"):
        assert (tmp_path / f"v321{suffix}").exists()
    conn.close()


def test_v321_strict_pit_requires_valuation_observation_date(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn, periods=300, codes=1)
    conn.execute("""UPDATE ml_features SET financial_disclosed_at='20230331',
                    valuation_per=10.0, valuation_pbr=1.0,
                    valuation_snapshot_date=NULL WHERE code='000001'""")
    conn.commit()
    data = pd.read_sql_query(
        "SELECT f.*, l.forward_return,l.benchmark_forward_return,l.excess_return,l.positive_excess,l.max_drawdown,l.label_available_at FROM ml_features f JOIN ml_labels l USING(code,feature_date,benchmark_code) WHERE l.horizon=20",
        conn)
    audit, summary = _financial_point_in_time_audit(conn, data, "069500")
    assert summary["status"] == "FINANCIAL_DISCLOSURE_PIT_PARTIAL"
    assert summary["verified"] is False
    assert audit.loc[audit["valuation_fact_present"], "valuation_date_valid"].eq(False).all()
    conn.close()


def test_v321_rejects_caps_and_glued_test_days_option(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn)
    with pytest.raises(ValueError, match="stock-cap"):
        run_ml_diagnostics_v321(conn, validation_days=40, test_days=40,
                                min_train_days=240, fold_days=40,
                                stock_cap=.16, output_prefix=str(tmp_path / "bad"))
    conn.close()
    proc = subprocess.run(
        [sys.executable, "-m", "src.main", "ml-diagnose-v321", "--test-days126"],
        cwd=str(__import__('pathlib').Path(__file__).resolve().parents[1]),
        capture_output=True, text=True)
    assert proc.returncode != 0
    assert "unrecognized arguments" in proc.stderr
