import numpy as np
import pandas as pd

from database.database import connect
from src.ml.diagnostics_v31 import (
    _apply_total_return_labels, _bootstrap_mean_ci, _read_total_return_history, _total_return_audit,
    run_ml_diagnostics_v31,
)
from tests.test_ml_diagnostics import _seed


def test_v31_ensemble_independent_metrics_and_reports(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn)
    prefix = tmp_path / "v31"
    summary = run_ml_diagnostics_v31(
        conn, validation_days=40, test_days=40, min_train_days=240,
        fold_days=40, output_prefix=str(prefix))

    assert summary["version"] == "3.1"
    assert summary["verdict"] == "RESEARCH_ONLY"
    assert summary["candidate_count"] == 53
    assert summary["research_seen_through"]
    assert summary["safety"] == "RESEARCH_AND_SHADOW_ONLY_NO_LIVE_ORDERS"
    assert summary["criteria"]["point_in_time_universe_verified"] is False
    assert summary["criteria"]["total_return_history_verified"] is False
    tournament = pd.read_csv(tmp_path / "v31_model_tournament.csv")
    validation = tournament[tournament["split"] == "validation"]
    assert len(validation) == 53
    assert {"nonoverlap_rank_ic", "nonoverlap_ic_ci_low",
            "independent_ic_periods"}.issubset(validation.columns)
    assert validation["feature_set"].str.contains("momentum").any()
    assert "financial_event_only" in set(validation["feature_set"])

    holdings = pd.read_csv(tmp_path / "v31_holding_contributions.csv", dtype={"code": str})
    assert holdings["entry_close"].notna().all()
    assert {"name", "position_status"}.issubset(holdings.columns)
    assert set(holdings["position_status"]) <= {"NEW", "HELD"}
    for suffix in (
        "_portfolio_transitions.csv", "_concentration.csv", "_portfolio_risk.csv",
        "_risk_warnings.csv",
        "_validation_ic.csv", "_published_test_ic.csv", "_total_return_audit.csv",
        "_universe_audit.csv", "_published_test_predictions.csv", "_verdict.json",
    ):
        assert (tmp_path / f"v31{suffix}").exists()
    conn.close()


def test_v31_total_return_input_is_strict_and_complete(tmp_path):
    invalid = tmp_path / "invalid.csv"
    invalid.write_text(
        "code,date,total_return_index,known_at,source\n"
        "005930,20240102,100,20240103,test\n", encoding="utf-8")
    _, verified, status = _read_total_return_history(str(invalid))
    assert verified is False
    assert status == "INVALID_TOTAL_RETURN_INPUT"

    valid = tmp_path / "valid.csv"
    valid.write_text(
        "code,date,total_return_index,known_at,source\n"
        "005930,20240102,100,20240102,test\n"
        "005930,20240130,110,20240130,test\n"
        "069500,20240102,200,20240102,test\n"
        "069500,20240130,210,20240130,test\n", encoding="utf-8")
    history, verified, status = _read_total_return_history(str(valid))
    assert verified is True
    assert status == "VERIFIED_TOTAL_RETURN_INPUT"
    data = pd.DataFrame([{
        "code": "005930", "feature_date": "20240102", "label_available_at": "20240130",
        "forward_return": 10.0, "benchmark_forward_return": 5.0,
    }])
    audit, summary = _total_return_audit(data, history, verified, "069500", 20)
    assert summary["total_return_verified"] is True
    assert summary["coverage_rate"] == 1.0
    np.testing.assert_allclose(audit["total_return"], [10.0])
    updated, applied, coverage = _apply_total_return_labels(
        data.assign(excess_return=5.0, positive_excess=1), history, verified, "069500")
    assert applied is True
    assert coverage == 1.0
    np.testing.assert_allclose(updated["forward_return"], [10.0])
    np.testing.assert_allclose(updated["benchmark_forward_return"], [5.0])


def test_v31_bootstrap_ci_is_reproducible():
    values = pd.Series([.1, .2, .3, .4, .5, .6])
    first = _bootstrap_mean_ci(values)
    second = _bootstrap_mean_ci(values)
    assert first == second
    assert first[0] < values.mean() < first[1]
