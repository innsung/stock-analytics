from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.ml.diagnostics_v2 import (
    BANK_SAFE_FINANCIAL_FEATURES, FINANCIAL_FEATURES, MARKET_FEATURES,
    PRICE_FEATURES, _rank_features, _split,
)
from src.ml.feature_store import FEATURE_COLUMNS
from src.ml.models import load_ml_dataset


UNIVERSE_COLUMNS = {
    "code", "effective_from", "effective_to", "selection_known_at",
    "listing_date", "delisting_date", "industry", "liquidity_eligible", "source",
}
NON_BANK_FINANCIAL_FEATURES = sorted(
    set(FINANCIAL_FEATURES) - set(BANK_SAFE_FINANCIAL_FEATURES))
FEATURE_SETS = {
    "price_only": PRICE_FEATURES,
    "financial_safe": FINANCIAL_FEATURES,
    "price_financial_safe": FEATURE_COLUMNS,
}


@dataclass(frozen=True)
class Candidate:
    model_name: str
    target_kind: str
    feature_set: str


def _normalise_date(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("-", "", regex=False).str.strip()


def _read_universe_history(path: str | None) -> tuple[pd.DataFrame, bool, str]:
    if not path:
        return pd.DataFrame(), False, "OBSERVED_DATA_ONLY"
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = UNIVERSE_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("V3 시점별 유니버스 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    date_columns = [
        "effective_from", "effective_to", "selection_known_at",
        "listing_date", "delisting_date",
    ]
    for column in date_columns:
        frame[column] = _normalise_date(frame[column])
    liquidity = frame["liquidity_eligible"].str.lower().str.strip()
    frame["liquidity_eligible"] = liquidity.map(
        {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False})
    required_dates = ["effective_from", "selection_known_at", "listing_date"]
    invalid = pd.Series(False, index=frame.index)
    for column in required_dates:
        invalid |= frame[column].str.len().ne(8)
    for column in ("effective_to", "delisting_date"):
        invalid |= frame[column].ne("") & frame[column].str.len().ne(8)
    invalid |= frame["selection_known_at"] > frame["effective_from"]
    invalid |= frame["listing_date"] > frame["effective_from"]
    invalid |= frame["effective_to"].ne("") & (
        frame["effective_to"] < frame["effective_from"])
    invalid |= frame["delisting_date"].ne("") & (
        frame["delisting_date"] < frame["listing_date"])
    invalid |= frame["liquidity_eligible"].isna()
    invalid |= frame["source"].str.strip().eq("")
    verified = bool(not frame.empty and not invalid.any())
    return frame, verified, "VERIFIED_HISTORY" if verified else "UNVERIFIED_HISTORY"


def _apply_universe_history(data: pd.DataFrame, history: pd.DataFrame
                            ) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    if history.empty:
        audit = data.groupby("code")["feature_date"].agg(
            first_observed="min", last_observed="max", raw_rows="size").reset_index()
        audit["eligible_rows"] = audit["raw_rows"]
        audit["excluded_rows"] = 0
        audit["coverage_complete"] = False
        audit["history_status"] = "OBSERVED_DATA_ONLY"
        return data.copy(), audit, False

    kept: list[pd.DataFrame] = []
    audit_rows: list[dict] = []
    coverage_complete = True
    for code, group in data.groupby("code", sort=True):
        intervals = history[history["code"] == code]
        eligible = pd.Series(False, index=group.index)
        covered = pd.Series(False, index=group.index)
        for row in intervals.itertuples(index=False):
            effective_end = row.effective_to or "99991231"
            delisting = row.delisting_date or "99991231"
            known_mask = (
                (group["feature_date"] >= row.effective_from)
                & (group["feature_date"] <= effective_end)
                & (group["feature_date"] >= row.selection_known_at)
                & (group["feature_date"] >= row.listing_date)
                & (group["feature_date"] <= delisting)
            )
            covered |= known_mask
            if bool(row.liquidity_eligible):
                eligible |= known_mask
        code_coverage = bool(not intervals.empty and covered.all())
        coverage_complete &= code_coverage
        selected = group[eligible]
        kept.append(selected)
        audit_rows.append({
            "code": code,
            "first_observed": group["feature_date"].min(),
            "last_observed": group["feature_date"].max(),
            "raw_rows": len(group), "eligible_rows": len(selected),
            "excluded_rows": len(group) - len(selected), "intervals": len(intervals),
            "coverage_complete": code_coverage,
            "history_status": "COVERED" if code_coverage else "INCOMPLETE_HISTORY",
        })
    eligible_data = pd.concat(kept, ignore_index=True) if kept else data.iloc[0:0].copy()
    return eligible_data, pd.DataFrame(audit_rows), bool(coverage_complete)


def _registered_lockbox_start(conn: sqlite3.Connection, benchmark_code: str,
                              horizon: int, requested: str | None) -> tuple[str | None, bool]:
    requested = requested.replace("-", "") if requested else None
    row = conn.execute(
        """SELECT lockbox_start FROM ml_lockbox_registry
           WHERE benchmark_code=? AND horizon=? AND diagnostic_version=3""",
        (benchmark_code, horizon)).fetchone()
    if row:
        registered = str(row[0])
        if requested and requested != registered:
            raise ValueError(
                f"V3 봉인시험 시작일은 이미 {registered}로 고정되었습니다. "
                "기존 봉인기간을 이동할 수 없습니다.")
        return registered, True
    if not requested:
        return None, False
    conn.execute(
        """INSERT INTO ml_lockbox_registry(
             benchmark_code,horizon,diagnostic_version,lockbox_start,registered_at)
           VALUES(?,?,3,?,?)""",
        (benchmark_code, horizon, requested, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    return requested, True


def _research_cutoff_and_lockbox_novelty(
        conn: sqlite3.Connection, benchmark_code: str, horizon: int,
        latest_observed: str, requested_lockbox: str | None) -> tuple[str, bool]:
    """Freeze what was already visible before a genuinely future V3 lockbox begins."""
    requested = requested_lockbox.replace("-", "") if requested_lockbox else None
    registered = conn.execute(
        """SELECT lockbox_start FROM ml_lockbox_registry
           WHERE benchmark_code=? AND horizon=? AND diagnostic_version=3""",
        (benchmark_code, horizon)).fetchone()
    row = conn.execute(
        """SELECT seen_through FROM ml_research_cutoff_registry
           WHERE benchmark_code=? AND horizon=? AND diagnostic_version=3""",
        (benchmark_code, horizon)).fetchone()
    if row:
        cutoff = str(row[0])
    else:
        # The first V3 execution necessarily exposes every currently stored labelled date.
        cutoff = latest_observed
        conn.execute(
            """INSERT INTO ml_research_cutoff_registry(
                 benchmark_code,horizon,diagnostic_version,seen_through,updated_at)
               VALUES(?,?,3,?,?)""",
            (benchmark_code, horizon, cutoff, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    if registered:
        return cutoff, str(registered[0]) > cutoff
    if requested:
        return cutoff, requested > cutoff
    # Until a lockbox is registered, every research run extends the seen-data boundary.
    cutoff = max(cutoff, latest_observed)
    conn.execute(
        """UPDATE ml_research_cutoff_registry SET seen_through=?,updated_at=?
           WHERE benchmark_code=? AND horizon=? AND diagnostic_version=3""",
        (cutoff, datetime.now(timezone.utc).isoformat(), benchmark_code, horizon))
    conn.commit()
    return cutoff, False


def _bank_safe(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    financial = result["industry"].fillna("").str.contains("금융|은행|증권|보험")
    result.loc[financial, NON_BANK_FINANCIAL_FEATURES] = np.nan
    return result


def _target(frame: pd.DataFrame, kind: str) -> pd.Series:
    if kind == "excess_regression":
        return frame["excess_return"].astype(float)
    if kind == "cross_sectional_rank":
        return frame.groupby("feature_date")["excess_return"].rank(pct=True)
    if kind == "industry_neutral_rank":
        return frame.groupby(["feature_date", "industry"], dropna=False)[
            "excess_return"].rank(pct=True)
    raise ValueError(f"지원하지 않는 학습 목표입니다: {kind}")


def _estimator(name: str):
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    if name == "ridge":
        return Pipeline([
            ("imputer", imputer), ("scale", StandardScaler()),
            ("model", Ridge(alpha=10.0)),
        ])
    if name == "elastic_net":
        return Pipeline([
            ("imputer", imputer), ("scale", StandardScaler()),
            ("model", ElasticNet(alpha=.01, l1_ratio=.25, max_iter=5000, random_state=42)),
        ])
    if name == "hist_gradient_boosting":
        return Pipeline([
            ("imputer", imputer),
            ("model", HistGradientBoostingRegressor(
                learning_rate=.05, max_iter=200, max_leaf_nodes=15,
                l2_regularization=1.0, random_state=42)),
        ])
    raise ValueError(f"지원하지 않는 회귀 모델입니다: {name}")


def _factor_score(frame: pd.DataFrame) -> np.ndarray:
    parts = pd.DataFrame(index=frame.index)
    parts["momentum"] = frame[["relative_20", "relative_60"]].mean(axis=1)
    parts["quality"] = frame[["roe", "operating_margin"]].mean(axis=1)
    parts["value"] = 1 - frame[["historical_pbr", "historical_per"]].mean(axis=1)
    parts["risk"] = 1 - frame[["volatility_20", "volatility_60"]].mean(axis=1)
    return parts.mean(axis=1, skipna=True).fillna(.5).to_numpy()


def _fit_predict(candidate: Candidate, train: pd.DataFrame,
                 test: pd.DataFrame) -> tuple[np.ndarray, object | None]:
    if candidate.model_name == "factor_composite":
        return _factor_score(test), None
    columns = FEATURE_SETS[candidate.feature_set]
    model = _estimator(candidate.model_name)
    model.fit(train[columns], _target(train, candidate.target_kind))
    return np.asarray(model.predict(test[columns]), dtype=float), model


def _daily_ic(frame: pd.DataFrame) -> tuple[float | None, float]:
    values = []
    for _, group in frame.groupby("feature_date"):
        if group["score"].nunique() < 2 or group["excess_return"].nunique() < 2:
            continue
        score_rank = group["score"].rank(method="average")
        return_rank = group["excess_return"].rank(method="average")
        values.append(float(score_rank.corr(return_rank)))
    if not values:
        return None, 0.0
    return float(np.mean(values)), float(np.mean(np.asarray(values) > 0))


def _portfolio(predictions: pd.DataFrame, horizon: int, commission: float,
               tax: float, slippage: float, scope: str
               ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summaries: list[dict] = []
    holdings: list[dict] = []
    periods: list[dict] = []
    dates = sorted(predictions["feature_date"].unique())[::horizon]
    for fraction in (.10, .20, .30):
        weights: dict[str, float] = {}
        model_equity = universe_equity = etf_equity = 1.0
        positive_universe = positive_etf = total_turnover = total_cost = 0.0
        for day in dates:
            cross = predictions[predictions["feature_date"] == day].sort_values(
                ["score", "code"], ascending=[False, True])
            if cross.empty:
                continue
            count = max(1, math.ceil(len(cross) * fraction))
            selected = cross.head(count).copy()
            target_weights = {str(code): 1 / count for code in selected["code"]}
            codes = set(weights) | set(target_weights)
            buys = sum(max(target_weights.get(c, 0) - weights.get(c, 0), 0) for c in codes)
            sells = sum(max(weights.get(c, 0) - target_weights.get(c, 0), 0) for c in codes)
            cost = buys * (commission + slippage) + sells * (commission + slippage + tax)
            gross = float(selected["forward_return"].mean())
            universe_return = float(cross["forward_return"].mean())
            etf_return = float(cross["benchmark_forward_return"].mean())
            net = gross - cost
            model_equity *= 1 + net / 100
            universe_equity *= 1 + universe_return / 100
            etf_equity *= 1 + etf_return / 100
            positive_universe += int(net > universe_return)
            positive_etf += int(net > etf_return)
            total_turnover += buys + sells
            total_cost += cost
            periods.append({
                "scope": scope, "feature_date": day, "top_fraction": fraction,
                "eligible_count": len(cross), "selected_count": count,
                "gross_return": gross, "net_return": net,
                "universe_equal_weight_return": universe_return,
                "etf_return": etf_return,
                "universe_excess_return": net - universe_return,
                "etf_excess_return": net - etf_return,
                "turnover": buys + sells, "cost_pct": cost,
            })
            for row in selected.itertuples(index=False):
                holdings.append({
                    "scope": scope, "feature_date": day, "top_fraction": fraction,
                    "code": row.code, "industry": row.industry, "weight": 1 / count,
                    "score": row.score, "entry_close": getattr(row, "close", np.nan),
                    "forward_return": row.forward_return,
                    "weighted_gross_contribution": row.forward_return / count,
                    "allocated_cost_pct": cost / count,
                    "weighted_net_contribution": (row.forward_return - cost) / count,
                })
            weights = target_weights
        count_periods = len(dates)
        summaries.append({
            "scope": scope, "top_fraction": fraction, "periods": count_periods,
            "net_return": (model_equity - 1) * 100,
            "universe_equal_weight_return": (universe_equity - 1) * 100,
            "etf_return": (etf_equity - 1) * 100,
            "universe_net_excess_return": (model_equity - universe_equity) * 100,
            "etf_net_excess_return": (model_equity - etf_equity) * 100,
            "positive_vs_universe_rate": positive_universe / count_periods if count_periods else 0,
            "positive_vs_etf_rate": positive_etf / count_periods if count_periods else 0,
            "turnover": total_turnover, "total_cost_pct": total_cost,
        })
    return pd.DataFrame(summaries), pd.DataFrame(holdings), pd.DataFrame(periods)


def _evaluate_candidate(candidate: Candidate, train: pd.DataFrame, test: pd.DataFrame,
                        horizon: int, commission: float, tax: float, slippage: float,
                        split: str) -> tuple[dict, pd.DataFrame, object | None]:
    scores, model = _fit_predict(candidate, train, test)
    prediction = test.copy()
    prediction["score"] = scores
    ic, positive_ic_rate = _daily_ic(prediction)
    portfolio, _, _ = _portfolio(
        prediction, horizon, commission, tax, slippage, split)
    top20 = portfolio[portfolio["top_fraction"] == .20].iloc[0]
    y = test["excess_return"].astype(float).to_numpy()
    # MAE/RMSE are meaningful only for raw excess-return regression.
    if candidate.target_kind == "excess_regression" and candidate.model_name != "factor_composite":
        mae = float(mean_absolute_error(y, scores))
        rmse = float(mean_squared_error(y, scores) ** .5)
    else:
        mae = rmse = None
    metric = {
        "split": split, "model_name": candidate.model_name,
        "target_kind": candidate.target_kind, "feature_set": candidate.feature_set,
        "samples": len(test), "daily_rank_ic": ic,
        "positive_daily_ic_rate": positive_ic_rate, "mae": mae, "rmse": rmse,
        "top20_universe_net_excess_return": float(top20["universe_net_excess_return"]),
        "top20_etf_net_excess_return": float(top20["etf_net_excess_return"]),
        "top20_positive_vs_universe_rate": float(top20["positive_vs_universe_rate"]),
        "top20_positive_vs_etf_rate": float(top20["positive_vs_etf_rate"]),
    }
    return metric, prediction, model


def _selection_score(metrics: pd.DataFrame) -> pd.Series:
    values = metrics.copy()
    for column in ("daily_rank_ic", "top20_universe_net_excess_return",
                   "top20_etf_net_excess_return", "positive_daily_ic_rate"):
        values[column] = pd.to_numeric(values[column], errors="coerce").fillna(-999)
        values[column + "_rank"] = values[column].rank(pct=True)
    return (
        values["daily_rank_ic_rank"] * .35
        + values["top20_universe_net_excess_return_rank"] * .30
        + values["top20_etf_net_excess_return_rank"] * .20
        + values["positive_daily_ic_rate_rank"] * .15
    )


def _return_audit(conn: sqlite3.Connection, data: pd.DataFrame, benchmark_code: str,
                  horizon: int) -> tuple[pd.DataFrame, dict]:
    dates = sorted(data["feature_date"].unique())[::horizon]
    sampled = data[data["feature_date"].isin(dates)].copy()
    prices = pd.read_sql_query(
        "SELECT code,date,close,source FROM stock_prices", conn, dtype={"code": str, "date": str})
    if prices.empty or sampled.empty:
        return pd.DataFrame(), {
            "rows": 0, "price_coverage_rate": 0.0, "label_match_rate": 0.0,
            "adjusted_price_verified": False, "dividend_verified": False,
            "status": "NO_RAW_PRICE_AUDIT_DATA",
        }
    prices["code"] = prices["code"].str.zfill(6)
    entry = prices.rename(columns={"date": "feature_date", "close": "entry_close",
                                   "source": "price_source"})
    exit_prices = prices.rename(columns={"date": "label_available_at", "close": "exit_close"})[
        ["code", "label_available_at", "exit_close"]]
    audit = sampled.merge(entry, on=["code", "feature_date"], how="left")
    audit = audit.merge(exit_prices, on=["code", "label_available_at"], how="left")
    benchmark = prices[prices["code"] == benchmark_code]
    benchmark_entry = benchmark[["date", "close"]].rename(
        columns={"date": "feature_date", "close": "benchmark_entry_close"})
    benchmark_exit = benchmark[["date", "close"]].rename(
        columns={"date": "label_available_at", "close": "benchmark_exit_close"})
    audit = audit.merge(benchmark_entry, on="feature_date", how="left")
    audit = audit.merge(benchmark_exit, on="label_available_at", how="left")
    audit["raw_forward_return"] = (audit["exit_close"] / audit["entry_close"] - 1) * 100
    audit["raw_benchmark_return"] = (
        audit["benchmark_exit_close"] / audit["benchmark_entry_close"] - 1) * 100
    audit["forward_return_difference"] = audit["raw_forward_return"] - audit["forward_return"]
    audit["benchmark_return_difference"] = (
        audit["raw_benchmark_return"] - audit["benchmark_forward_return"])
    audit["label_return_match"] = audit["forward_return_difference"].abs() <= 1e-8
    audit["benchmark_return_match"] = audit["benchmark_return_difference"].abs() <= 1e-8
    audit["adjusted_price_status"] = "UNVERIFIED_RAW_CLOSE_ONLY"
    audit["dividend_status"] = "NOT_AVAILABLE"
    audit["simple_net_return"] = audit["forward_return"]
    columns = [
        "code", "feature_date", "label_available_at", "entry_close", "exit_close",
        "raw_forward_return", "forward_return", "forward_return_difference",
        "benchmark_entry_close", "benchmark_exit_close", "raw_benchmark_return",
        "benchmark_forward_return", "benchmark_return_difference", "label_return_match",
        "benchmark_return_match", "price_source", "adjusted_price_status",
        "dividend_status", "simple_net_return",
    ]
    coverage = audit[["entry_close", "exit_close", "benchmark_entry_close",
                      "benchmark_exit_close"]].notna().all(axis=1)
    comparable = audit[coverage]
    summary = {
        "rows": int(len(audit)), "comparable_rows": int(len(comparable)),
        "price_coverage_rate": float(coverage.mean()) if len(audit) else 0.0,
        "label_match_rate": float(comparable["label_return_match"].mean())
        if len(comparable) else 0.0,
        "benchmark_match_rate": float(comparable["benchmark_return_match"].mean())
        if len(comparable) else 0.0,
        "adjusted_price_verified": False, "dividend_verified": False,
        "status": "ARITHMETIC_CHECKED_CORPORATE_ACTIONS_UNVERIFIED",
    }
    return audit[columns], summary


def _monotonic(portfolio: pd.DataFrame, scope: str) -> bool:
    rows = portfolio[portfolio["scope"] == scope].set_index("top_fraction")
    if not {.1, .2, .3}.issubset(rows.index):
        return False
    values = rows["universe_net_excess_return"]
    return bool(values.loc[.1] >= values.loc[.2] >= values.loc[.3])


def run_ml_diagnostics_v3(
        conn: sqlite3.Connection, horizon: int = 20, benchmark_code: str = "069500",
        validation_days: int = 126, test_days: int = 126, min_train_days: int = 504,
        fold_days: int = 126, commission: float = .015, tax: float = .18,
        slippage: float = .05, output_prefix: str = "ml_v3_h20",
        lockbox_start: str | None = None, universe_history_csv: str | None = None,
        rank_scope: str = "market") -> dict:
    data = load_ml_dataset(conn, horizon, benchmark_code)
    if data.empty:
        raise ValueError("V3 진단 데이터가 없습니다. build-feature-store를 먼저 실행하세요.")
    original_codes = set(data["code"].astype(str).str.zfill(6))
    data["code"] = data["code"].astype(str).str.zfill(6)
    history, history_valid, history_status = _read_universe_history(universe_history_csv)
    data, universe_audit, full_coverage = _apply_universe_history(data, history)
    universe_verified = bool(history_valid and full_coverage and not data.empty)
    if data.empty:
        raise ValueError("시점별 유니버스 적용 후 학습 가능한 행이 없습니다.")
    if set(data["code"].unique()) - original_codes:
        raise AssertionError("유니버스 적용 중 원래 없던 종목이 추가되었습니다.")
    data = _bank_safe(_rank_features(data, rank_scope))
    research_cutoff, fresh_v3_lockbox = _research_cutoff_and_lockbox_novelty(
        conn, benchmark_code, horizon, str(data["feature_date"].max()), lockbox_start)
    existing_v3_lockbox = conn.execute(
        """SELECT 1 FROM ml_lockbox_registry
           WHERE benchmark_code=? AND horizon=? AND diagnostic_version=3""",
        (benchmark_code, horizon)).fetchone()
    if lockbox_start and not fresh_v3_lockbox and not existing_v3_lockbox:
        # Do not permanently register an already-seen interval as a new lockbox.
        registered_lockbox, lockbox_registered = None, False
    else:
        registered_lockbox, lockbox_registered = _registered_lockbox_start(
            conn, benchmark_code, horizon, lockbox_start)
    dates, validation_start, test_start, train, validation, lockbox = _split(
        data, validation_days, test_days, registered_lockbox)

    candidates = [
        Candidate(model, target, features)
        for model in ("ridge", "elastic_net", "hist_gradient_boosting")
        for target in ("excess_regression", "cross_sectional_rank", "industry_neutral_rank")
        for features in FEATURE_SETS
    ] + [Candidate("factor_composite", "factor_rule", "price_financial_safe")]
    tournament_rows: list[dict] = []
    validation_predictions: dict[Candidate, pd.DataFrame] = {}
    for candidate in candidates:
        metric, prediction, _ = _evaluate_candidate(
            candidate, train, validation, horizon, commission, tax, slippage, "validation")
        tournament_rows.append(metric)
        validation_predictions[candidate] = prediction
    tournament = pd.DataFrame(tournament_rows)
    tournament["selection_score"] = _selection_score(tournament)
    tournament = tournament.sort_values(
        ["selection_score", "daily_rank_ic"], ascending=[False, False]).reset_index(drop=True)
    selected = Candidate(
        str(tournament.iloc[0]["model_name"]), str(tournament.iloc[0]["target_kind"]),
        str(tournament.iloc[0]["feature_set"]))

    development = data[(data["feature_date"] < test_start)
                       & (data["label_available_at"] < test_start)]
    lock_metric, lock_predictions, _ = _evaluate_candidate(
        selected, development, lockbox, horizon, commission, tax, slippage, "lockbox_test")
    tournament = pd.concat([tournament, pd.DataFrame([lock_metric])], ignore_index=True)

    development_dates = dates[dates < validation_start]
    walk_rows: list[dict] = []
    walk_predictions: list[pd.DataFrame] = []
    for offset in range(min_train_days, len(development_dates), fold_days):
        fold_dates = development_dates[offset:min(offset + fold_days, len(development_dates))]
        if len(fold_dates) < max(20, fold_days // 3):
            continue
        fold_start = fold_dates[0]
        fold_train = data[(data["feature_date"] < fold_start)
                          & (data["label_available_at"] < fold_start)]
        fold_test = data[data["feature_date"].isin(fold_dates)]
        if fold_train.empty or fold_test.empty:
            continue
        metric, prediction, _ = _evaluate_candidate(
            selected, fold_train, fold_test, horizon, commission, tax, slippage,
            f"walk_forward_{len(walk_rows) + 1}")
        metric.update({
            "fold": len(walk_rows) + 1, "train_start": fold_train["feature_date"].min(),
            "train_end": fold_train["feature_date"].max(),
            "test_start": fold_dates[0], "test_end": fold_dates[-1],
        })
        walk_rows.append(metric)
        walk_predictions.append(prediction.assign(fold=len(walk_rows)))
    walk = pd.DataFrame(walk_rows)
    walk_prediction_frame = (pd.concat(walk_predictions, ignore_index=True)
                             if walk_predictions else pd.DataFrame())

    portfolio_frames: list[pd.DataFrame] = []
    holding_frames: list[pd.DataFrame] = []
    period_frames: list[pd.DataFrame] = []
    for scope, predictions in (
            ("walk_forward_pre_validation", walk_prediction_frame),
            ("validation", validation_predictions[selected]),
            ("lockbox_test", lock_predictions)):
        if predictions.empty:
            continue
        p, h, d = _portfolio(predictions, horizon, commission, tax, slippage, scope)
        portfolio_frames.append(p); holding_frames.append(h); period_frames.append(d)
    portfolios = pd.concat(portfolio_frames, ignore_index=True)
    holdings = pd.concat(holding_frames, ignore_index=True)
    portfolio_periods = pd.concat(period_frames, ignore_index=True)

    return_audit, return_audit_summary = _return_audit(
        conn, data, benchmark_code, horizon)
    return_verified = bool(
        return_audit_summary["price_coverage_rate"] >= .999
        and return_audit_summary["label_match_rate"] >= .999
        and return_audit_summary["benchmark_match_rate"] >= .999
        and return_audit_summary["adjusted_price_verified"]
        and return_audit_summary["dividend_verified"])
    walk_independent = bool(walk.empty or (
        walk["test_end"].max() < validation_start and walk["test_end"].max() < test_start))
    walk_ic = float(walk["daily_rank_ic"].dropna().mean()) if not walk.empty else 0.0
    fold_universe_rate = float(
        (walk["top20_universe_net_excess_return"] > 0).mean()) if not walk.empty else 0.0
    walk_top20 = portfolios[(portfolios["scope"] == "walk_forward_pre_validation")
                            & (portfolios["top_fraction"] == .20)]
    lock_top20 = portfolios[(portfolios["scope"] == "lockbox_test")
                            & (portfolios["top_fraction"] == .20)]
    criteria = {
        "independent_evaluation_periods": walk_independent,
        "immutable_v3_lockbox_registered": lockbox_registered,
        "fresh_v3_lockbox_after_research_cutoff": fresh_v3_lockbox,
        "point_in_time_universe_verified": universe_verified,
        "return_calculation_fully_verified": return_verified,
        "validation_daily_rank_ic_positive": bool(
            pd.notna(tournament.iloc[0]["daily_rank_ic"])
            and tournament.iloc[0]["daily_rank_ic"] > 0),
        "walk_forward_daily_rank_ic_positive": walk_ic > 0,
        "walk_forward_dual_benchmark_top20_positive": bool(
            not walk_top20.empty
            and walk_top20.iloc[0]["universe_net_excess_return"] > 0
            and walk_top20.iloc[0]["etf_net_excess_return"] > 0),
        "majority_folds_universe_excess_positive": fold_universe_rate > .5,
        "validation_top_fraction_monotonic": _monotonic(portfolios, "validation"),
        "lockbox_dual_benchmark_top20_positive": bool(
            not lock_top20.empty
            and lock_top20.iloc[0]["universe_net_excess_return"] > 0
            and lock_top20.iloc[0]["etf_net_excess_return"] > 0),
    }
    verdict = "ADOPT" if all(criteria.values()) else "RESEARCH_ONLY"
    independence = pd.DataFrame([
        {"check": "walk_forward_before_validation", "passed": walk_independent,
         "latest_walk_test_end": None if walk.empty else walk["test_end"].max(),
         "validation_start": validation_start, "lockbox_start": test_start},
        {"check": "label_purge_at_boundaries", "passed": True,
         "latest_walk_test_end": None, "validation_start": validation_start,
         "lockbox_start": test_start},
        {"check": "immutable_v3_lockbox_registered", "passed": lockbox_registered,
         "latest_walk_test_end": None, "validation_start": validation_start,
         "lockbox_start": test_start},
    ])
    summary = {
        "version": 3, "verdict": verdict,
        "selected_model": selected.model_name,
        "selected_target": selected.target_kind,
        "selected_feature_set": selected.feature_set,
        "rank_scope": rank_scope, "horizon": horizon,
        "validation_period": [validation["feature_date"].min(), validation["feature_date"].max()],
        "lockbox_period": [lockbox["feature_date"].min(), lockbox["feature_date"].max()],
        "walk_forward_period": [None if walk.empty else walk["test_start"].min(),
                                None if walk.empty else walk["test_end"].max()],
        "walk_forward_folds": int(len(walk)),
        "universe_history_status": history_status,
        "research_seen_through": research_cutoff,
        "return_audit": return_audit_summary,
        "criteria": criteria,
        "cost_assumptions_pct": {
            "commission_one_way": commission, "sell_tax": tax,
            "slippage_one_way": slippage,
        },
        "safety": "RESEARCH_AND_SHADOW_ONLY_NO_LIVE_ORDERS",
        "note": "V2 lockbox results are not used to select the V3 model.",
    }
    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)

    def save(frame: pd.DataFrame, suffix: str) -> None:
        frame.to_csv(prefix.with_name(prefix.name + suffix), index=False, encoding="utf-8-sig")

    save(tournament, "_model_tournament.csv")
    save(walk, "_walk_forward.csv")
    save(portfolios, "_dual_benchmark_portfolios.csv")
    save(portfolio_periods, "_portfolio_periods.csv")
    save(holdings, "_holding_contributions.csv")
    save(return_audit, "_return_audit.csv")
    save(universe_audit, "_universe_audit.csv")
    save(independence, "_independence_audit.csv")
    prediction_columns = [
        "code", "feature_date", "industry", "forward_return",
        "benchmark_forward_return", "excess_return", "score",
    ]
    save(lock_predictions[prediction_columns], "_lockbox_predictions.csv")
    prefix.with_name(prefix.name + "_verdict.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
