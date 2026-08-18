import pandas as pd

from database.database import connect
from src.ml.diagnostics_v3 import (
    _read_universe_history, _registered_lockbox_start,
    _research_cutoff_and_lockbox_novelty, run_ml_diagnostics_v3,
)
from tests.test_ml_diagnostics import _seed


def test_v3_tournament_dual_benchmark_and_audits(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed(conn)
    prefix = tmp_path / "v3"
    summary = run_ml_diagnostics_v3(
        conn, validation_days=40, test_days=40, min_train_days=240,
        fold_days=40, output_prefix=str(prefix))

    assert summary["version"] == 3
    assert summary["verdict"] == "RESEARCH_ONLY"
    assert summary["criteria"]["independent_evaluation_periods"] is True
    assert summary["criteria"]["immutable_v3_lockbox_registered"] is False
    assert summary["criteria"]["fresh_v3_lockbox_after_research_cutoff"] is False
    assert summary["criteria"]["point_in_time_universe_verified"] is False
    assert summary["criteria"]["return_calculation_fully_verified"] is False
    assert summary["safety"] == "RESEARCH_AND_SHADOW_ONLY_NO_LIVE_ORDERS"

    tournament = pd.read_csv(tmp_path / "v3_model_tournament.csv")
    validation = tournament[tournament["split"] == "validation"]
    assert len(validation) == 28
    assert {"excess_regression", "cross_sectional_rank",
            "industry_neutral_rank", "factor_rule"} == set(validation["target_kind"])
    portfolios = pd.read_csv(tmp_path / "v3_dual_benchmark_portfolios.csv")
    assert {"universe_net_excess_return", "etf_net_excess_return"}.issubset(portfolios.columns)
    assert set(portfolios["top_fraction"].round(1)) == {.1, .2, .3}
    walk = pd.read_csv(tmp_path / "v3_walk_forward.csv", dtype=str)
    assert walk["test_end"].max() < summary["validation_period"][0]
    assert walk["test_end"].max() < summary["lockbox_period"][0]

    for suffix in (
        "_model_tournament.csv", "_walk_forward.csv",
        "_dual_benchmark_portfolios.csv", "_portfolio_periods.csv",
        "_holding_contributions.csv", "_return_audit.csv",
        "_universe_audit.csv", "_independence_audit.csv",
        "_lockbox_predictions.csv", "_verdict.json",
    ):
        assert (tmp_path / f"v3{suffix}").exists()
    conn.close()


def test_v3_history_schema_and_lockbox_are_strict(tmp_path):
    history = tmp_path / "history.csv"
    history.write_text(
        "code,effective_from,effective_to,selection_known_at,listing_date,"
        "delisting_date,industry,liquidity_eligible,source\n"
        "005930,20210104,,20210104,19750611,,반도체,true,test-fixture\n",
        encoding="utf-8")
    frame, verified, status = _read_universe_history(str(history))
    assert verified is True
    assert status == "VERIFIED_HISTORY"
    assert bool(frame.iloc[0]["liquidity_eligible"]) is True

    conn = connect(tmp_path / "lock.db")
    cutoff, fresh = _research_cutoff_and_lockbox_novelty(
        conn, "069500", 20, "20260807", None)
    assert (cutoff, fresh) == ("20260807", False)
    cutoff, fresh = _research_cutoff_and_lockbox_novelty(
        conn, "069500", 20, "20260930", "20260810")
    assert (cutoff, fresh) == ("20260807", True)
    registered, fixed = _registered_lockbox_start(conn, "069500", 20, "20260810")
    assert (registered, fixed) == ("20260810", True)
    try:
        _registered_lockbox_start(conn, "069500", 20, "20260901")
    except ValueError as exc:
        assert "이미 20260810로 고정" in str(exc)
    else:
        raise AssertionError("V3 봉인기간 이동이 거부되지 않았습니다.")
    conn.close()
