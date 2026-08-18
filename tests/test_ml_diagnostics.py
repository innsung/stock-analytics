import sqlite3

import joblib
import numpy as np
import pandas as pd

from database.database import connect
from src.ml.diagnostics import financial_missingness_reports, run_ml_diagnostics
from src.ml.diagnostics_v2 import run_ml_diagnostics_v2
from src.ml.diagnostics_v2 import _pipeline
from src.ml.feature_store import FEATURE_COLUMNS


def _seed(conn: sqlite3.Connection, periods=380, codes=3):
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
                              "forward_return": excess + .2,
                              "benchmark_forward_return": .2,
                              "excess_return": excess,
                              "positive_excess": int(excess > 0),
                              "max_drawdown": min(excess, 0),
                              "label_available_at": dates[index + 20].strftime("%Y%m%d"),
                              "generated_at": "2026-01-01T00:00:00+00:00"})
                conn.execute(
                    f"INSERT INTO ml_labels({','.join(label_columns)}) "
                    f"VALUES({','.join('?' for _ in label_columns)})",
                    tuple(label[column] for column in label_columns))
    conn.commit()


def test_diagnostic_suite_writes_verdict_and_reports(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn)
    prefix = tmp_path / "diagnostic"
    summary = run_ml_diagnostics(
        conn, validation_days=40, test_days=40, min_train_days=280,
        fold_days=40, output_prefix=str(prefix))
    assert summary["verdict"] in {"ADOPT", "RESEARCH_ONLY"}
    assert len(summary["criteria"]) == 5
    assert (tmp_path / "diagnostic_metrics.csv").exists()
    assert (tmp_path / "diagnostic_portfolios.csv").exists()
    assert (tmp_path / "diagnostic_verdict.json").exists()
    portfolios = pd.read_csv(tmp_path / "diagnostic_portfolios.csv")
    assert set(portfolios["top_fraction"].round(1)) == {.1, .2, .3}
    assert set(portfolios["scope"]) == {"walk_forward", "lockbox_test"}
    items, features = financial_missingness_reports(conn, ["000001"], 2021, 2021)
    assert len(items) == 8
    assert len(features) == len(FEATURE_COLUMNS)
    conn.close()


def test_corrected_diagnostics_keep_walk_forward_before_validation_and_lockbox(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn)
    conn.execute("UPDATE ml_features SET industry='금융' WHERE code='000001'")
    conn.commit()
    prefix = tmp_path / "corrected"
    lockbox_start = pd.bdate_range("2023-01-02", periods=380)[340].strftime("%Y%m%d")
    summary = run_ml_diagnostics_v2(
        conn, validation_days=40, test_days=40, min_train_days=280,
        fold_days=40, lockbox_start=lockbox_start, output_prefix=str(prefix))
    assert summary["criteria"]["independent_evaluation_periods"] is True
    assert summary["criteria"]["immutable_lockbox_registered"] is True
    assert summary["criteria"]["point_in_time_universe_verified"] is False
    assert summary["safety"] == "RESEARCH_AND_SHADOW_ONLY_NO_LIVE_ORDERS"
    walk = pd.read_csv(tmp_path / "corrected_walk_forward.csv", dtype=str)
    assert walk["test_end"].max() < summary["validation_period"][0]
    assert walk["test_end"].max() < summary["lockbox_period"][0]
    metrics = pd.read_csv(tmp_path / "corrected_metrics.csv")
    validation = metrics[metrics["split"] == "validation"]
    assert set(validation["missing_indicators"].astype(str).str.lower()) == {"true", "false"}
    groups = pd.read_csv(tmp_path / "corrected_financial_nonfinancial.csv")
    assert set(groups["group"]) == {"financial", "non_financial"}
    assert set(groups.loc[groups["group"] == "financial", "feature_set"]) == {"bank_safe"}
    for suffix in (
        "_portfolios.csv", "_holding_contributions.csv", "_concentration.csv",
        "_financial_nonfinancial.csv", "_market_regimes.csv", "_universe_audit.csv",
        "_independence_audit.csv", "_feature_coefficients.csv", "_verdict.json",
    ):
        assert (tmp_path / f"corrected{suffix}").exists()
    conn.close()


def test_corrected_diagnostics_verifies_complete_point_in_time_history(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn)
    history = tmp_path / "history.csv"
    history.write_text(
        "code,eligible_from,eligible_to,selection_known_at,source\n"
        "000001,20230102,,20230102,test-fixture\n"
        "000002,20230102,,20230102,test-fixture\n"
        "000003,20230102,,20230102,test-fixture\n",
        encoding="utf-8")
    lockbox_start = pd.bdate_range("2023-01-02", periods=380)[340].strftime("%Y%m%d")
    summary = run_ml_diagnostics_v2(
        conn, validation_days=40, test_days=40, min_train_days=280,
        fold_days=40, lockbox_start=lockbox_start,
        universe_history_csv=str(history), output_prefix=str(tmp_path / "verified"))
    assert summary["universe_history_status"] == "VERIFIED_HISTORY"
    assert summary["criteria"]["point_in_time_universe_verified"] is True
    with np.testing.assert_raises_regex(ValueError, "이미 .*고정"):
        run_ml_diagnostics_v2(
            conn, validation_days=40, test_days=40, min_train_days=280,
            fold_days=40, lockbox_start="20240101",
            universe_history_csv=str(history), output_prefix=str(tmp_path / "moved"))
    conn.close()


def test_ml_pipeline_joblib_round_trip(tmp_path):
    frame = pd.DataFrame({"roe": [1.0, np.nan, 3.0, 4.0],
                          "historical_pbr": [0.8, 1.0, np.nan, 1.2]})
    target = pd.Series([0, 0, 1, 1])
    model = _pipeline("logistic_regression", True).fit(frame, target)
    artifact = tmp_path / "roundtrip.joblib"
    joblib.dump(model, artifact)
    restored = joblib.load(artifact)
    np.testing.assert_allclose(model.predict_proba(frame), restored.predict_proba(frame))
