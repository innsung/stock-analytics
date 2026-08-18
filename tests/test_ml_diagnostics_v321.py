import subprocess
import sys
import sqlite3

import numpy as np
import pandas as pd
import pytest

from database.database import connect
from src.ml.feature_store import FEATURE_COLUMNS
from src.ml.diagnostics_v321 import (
    RESEARCH_SEEN_THROUGH,
    _candidates,
    _financial_point_in_time_audit,
    run_ml_diagnostics_v321,
)

def _seed(conn: sqlite3.Connection, periods: int = 380, codes: int = 3) -> None:
    """Create deterministic V3.2.1 diagnostic fixtures."""
    dates = pd.bdate_range("2023-01-02", periods=periods)
    feature_columns = [row[1] for row in conn.execute("PRAGMA table_info(ml_features)")]
    label_columns = [row[1] for row in conn.execute("PRAGMA table_info(ml_labels)")]
    rng = np.random.default_rng(7)
    for code_index in range(codes):
        code = f"{code_index + 1:06d}"
        signal = rng.normal(size=periods)
        for index, day in enumerate(dates):
            feature = {column: None for column in feature_columns}
            feature.update({"code": code, "feature_date": day.strftime("%Y%m%d"),
                            "benchmark_code": "069500", "industry": f"업종{code_index}",
                            "close": 10_000 + index, "volume": 100_000,
                            "generated_at": "2026-01-01T00:00:00+00:00"})
            for feature_index, column in enumerate(FEATURE_COLUMNS):
                feature[column] = signal[index] + feature_index * .01
            conn.execute(
                f"INSERT INTO ml_features({','.join(feature_columns)}) "
                f"VALUES({','.join('?' for _ in feature_columns)})",
                tuple(feature[column] for column in feature_columns))
            if index + 20 < periods:
                excess = signal[index] + rng.normal(scale=.8)
                label = {column: None for column in label_columns}
                label.update({"code": code, "feature_date": day.strftime("%Y%m%d"),
                              "benchmark_code": "069500", "horizon": 20,
                              "forward_return": excess + .2, "benchmark_forward_return": .2,
                              "excess_return": excess, "positive_excess": int(excess > 0),
                              "max_drawdown": min(excess, 0),
                              "label_available_at": dates[index + 20].strftime("%Y%m%d"),
                              "generated_at": "2026-01-01T00:00:00+00:00"})
                conn.execute(
                    f"INSERT INTO ml_labels({','.join(label_columns)}) "
                    f"VALUES({','.join('?' for _ in label_columns)})",
                    tuple(label[column] for column in label_columns))
    conn.commit()


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
