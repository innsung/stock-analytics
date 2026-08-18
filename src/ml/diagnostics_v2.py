from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.ml.feature_store import FEATURE_COLUMNS
from src.ml.models import load_ml_dataset


PRICE_FEATURES = FEATURE_COLUMNS[:17]
FINANCIAL_FEATURES = FEATURE_COLUMNS[17:]
BANK_SAFE_FINANCIAL_FEATURES = [
    "roe", "reported_eps", "estimated_bps", "historical_per", "historical_pbr",
]
MARKET_FEATURES = {
    "benchmark_return_20", "benchmark_ma_120_gap", "benchmark_volatility_60",
    "market_regime",
}
FEATURE_SETS = {
    "price_only": PRICE_FEATURES,
    "financial_only": FINANCIAL_FEATURES,
    "price_financial": FEATURE_COLUMNS,
}


@dataclass(frozen=True)
class Metric:
    split: str
    group: str
    model_name: str
    feature_set: str
    missing_indicators: bool
    sample_count: int
    positive_rate: float
    roc_auc: float | None
    accuracy: float
    brier: float
    dummy_brier: float
    brier_skill_score: float


def _safe_auc(target, probabilities) -> float | None:
    return None if len(np.unique(target)) < 2 else float(roc_auc_score(target, probabilities))


def _pipeline(model_name: str, missing_indicators: bool):
    if model_name == "dummy_prior":
        return DummyClassifier(strategy="prior")
    imputer = SimpleImputer(
        strategy="median", add_indicator=missing_indicators, keep_empty_features=True)
    if model_name == "logistic_regression":
        return Pipeline([
            ("imputer", imputer),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(
                max_iter=2000, class_weight="balanced", random_state=42)),
        ])
    if model_name == "hist_gradient_boosting":
        return Pipeline([
            ("imputer", imputer),
            ("model", HistGradientBoostingClassifier(
                learning_rate=.05, max_iter=200, max_leaf_nodes=15,
                l2_regularization=1.0, random_state=42)),
        ])
    raise ValueError(f"지원하지 않는 모델입니다: {model_name}")


def _rank_features(data: pd.DataFrame, scope: str) -> pd.DataFrame:
    """Use only same-day observations; no future or target information enters ranks."""
    ranked = data.copy()
    keys = ["feature_date"] if scope == "market" else ["feature_date", "industry"]
    columns = [column for column in FEATURE_COLUMNS if column not in MARKET_FEATURES]
    ranked[columns] = ranked.groupby(keys, dropna=False)[columns].rank(
        method="average", pct=True, na_option="keep")
    return ranked


def _read_universe_history(path: str | None) -> tuple[pd.DataFrame, bool, str]:
    required = {"code", "eligible_from", "eligible_to", "selection_known_at", "source"}
    if not path:
        return pd.DataFrame(), False, "OBSERVED_DATA_ONLY"
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("시점별 유니버스 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    for column in ("eligible_from", "eligible_to", "selection_known_at"):
        frame[column] = frame[column].str.replace("-", "", regex=False).str.strip()
    invalid = (
        (frame["eligible_from"].str.len() != 8) |
        ((frame["eligible_to"] != "") & (frame["eligible_to"].str.len() != 8)) |
        (frame["selection_known_at"].str.len() != 8) |
        (frame["selection_known_at"] > frame["eligible_from"]) |
        (frame["source"].str.strip() == "")
    )
    verified = bool(not frame.empty and not invalid.any())
    return frame, verified, "VERIFIED_HISTORY" if verified else "UNVERIFIED_HISTORY"


def _apply_universe_history(data: pd.DataFrame, history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if history.empty:
        audit = (data.groupby("code")["feature_date"].agg(
            first_observed="min", last_observed="max", eligible_rows="size").reset_index())
        audit["history_status"] = "OBSERVED_DATA_ONLY"
        return data, audit
    kept = []
    audit_rows = []
    for code, group in data.groupby("code"):
        intervals = history[history["code"] == code]
        mask = pd.Series(False, index=group.index)
        for row in intervals.itertuples(index=False):
            end = row.eligible_to or "99991231"
            mask |= ((group["feature_date"] >= row.eligible_from) &
                     (group["feature_date"] <= end) &
                     (group["feature_date"] >= row.selection_known_at))
        selected = group[mask]
        kept.append(selected)
        audit_rows.append({
            "code": code, "first_observed": group["feature_date"].min(),
            "last_observed": group["feature_date"].max(), "raw_rows": len(group),
            "eligible_rows": len(selected), "excluded_rows": len(group) - len(selected),
            "intervals": len(intervals),
            "history_status": "COVERED" if not intervals.empty else "MISSING_CODE_HISTORY",
        })
    return pd.concat(kept, ignore_index=True), pd.DataFrame(audit_rows)


def _split(data: pd.DataFrame, validation_days: int, test_days: int,
           lockbox_start: str | None):
    dates = np.array(sorted(data["feature_date"].unique()))
    if lockbox_start:
        lockbox_start = lockbox_start.replace("-", "")
        test_index = int(np.searchsorted(dates, lockbox_start, side="left"))
        if test_index >= len(dates):
            raise ValueError("--lockbox-start 이후의 데이터가 없습니다.")
    else:
        if len(dates) <= test_days:
            raise ValueError("봉인시험 거래일이 부족합니다.")
        test_index = len(dates) - test_days
    validation_index = test_index - validation_days
    if validation_index < 252:
        raise ValueError("학습·검증·봉인시험 분리에 필요한 거래일이 부족합니다.")
    validation_start = dates[validation_index]
    test_start = dates[test_index]
    train = data[(data["feature_date"] < validation_start) &
                 (data["label_available_at"] < validation_start)]
    validation = data[(data["feature_date"] >= validation_start) &
                      (data["feature_date"] < test_start) &
                      (data["label_available_at"] < test_start)]
    lockbox = data[data["feature_date"] >= test_start]
    if min(len(train), len(validation), len(lockbox)) == 0:
        raise ValueError("학습·검증·봉인시험 중 빈 구간이 있습니다.")
    return dates, validation_start, test_start, train, validation, lockbox


def _registered_lockbox_start(conn: sqlite3.Connection, benchmark_code: str,
                              horizon: int, requested: str | None) -> tuple[str | None, bool]:
    requested = requested.replace("-", "") if requested else None
    row = conn.execute(
        """SELECT lockbox_start FROM ml_lockbox_registry
           WHERE benchmark_code=? AND horizon=? AND diagnostic_version=2""",
        (benchmark_code, horizon)).fetchone()
    if row:
        registered = str(row[0])
        if requested and requested != registered:
            raise ValueError(
                f"봉인시험 시작일은 이미 {registered}로 고정되었습니다. "
                "기존 봉인기간을 이동할 수 없습니다.")
        return registered, True
    if not requested:
        return None, False
    conn.execute(
        """INSERT INTO ml_lockbox_registry(
             benchmark_code,horizon,diagnostic_version,lockbox_start,registered_at)
           VALUES(?,?,2,?,?)""",
        (benchmark_code, horizon, requested, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    return requested, True


def _evaluate(split: str, group: str, model_name: str, feature_set: str,
              missing_indicators: bool, frame: pd.DataFrame,
              probabilities: np.ndarray, dummy_probabilities: np.ndarray
              ) -> tuple[dict, pd.DataFrame]:
    target = frame["positive_excess"].astype(int).to_numpy()
    brier = float(brier_score_loss(target, probabilities))
    dummy_brier = float(brier_score_loss(target, dummy_probabilities))
    metric = Metric(
        split, group, model_name, feature_set, missing_indicators, len(frame),
        float(target.mean()), _safe_auc(target, probabilities),
        float(accuracy_score(target, probabilities >= .5)), brier, dummy_brier,
        (1 - brier / dummy_brier) if dummy_brier else 0.0,
    )
    output_columns = [
        "code", "feature_date", "industry", "market_regime", "benchmark_volatility_60",
        "positive_excess",
        "forward_return", "benchmark_forward_return", "excess_return", "max_drawdown",
    ]
    output = frame[output_columns].copy()
    output["split"] = split
    output["group"] = group
    output["model_name"] = model_name
    output["feature_set"] = feature_set
    output["missing_indicators"] = missing_indicators
    output["probability"] = probabilities
    return asdict(metric), output


def _fit_evaluate(train: pd.DataFrame, test: pd.DataFrame, columns: list[str],
                  split: str, group: str, model_name: str, feature_set: str,
                  missing_indicators: bool):
    dummy = _pipeline("dummy_prior", False).fit(
        train[columns], train["positive_excess"].astype(int))
    model = _pipeline(model_name, missing_indicators).fit(
        train[columns], train["positive_excess"].astype(int))
    probabilities = model.predict_proba(test[columns])[:, 1]
    dummy_probabilities = dummy.predict_proba(test[columns])[:, 1]
    metric, predictions = _evaluate(
        split, group, model_name, feature_set, missing_indicators, test,
        probabilities, dummy_probabilities)
    return metric, predictions, model


def _portfolio(predictions: pd.DataFrame, horizon: int, commission: float,
               tax: float, slippage: float, scope: str
               ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summaries, holdings, concentration = [], [], []
    dates = sorted(predictions["feature_date"].unique())[::horizon]
    for fraction in (.10, .20, .30):
        weights: dict[str, float] = {}
        equity = benchmark_equity = peak = 1.0
        mdd = 0.0
        total_turnover = total_cost = 0.0
        positive_periods = periods = 0
        for day in dates:
            cross = predictions[predictions["feature_date"] == day].sort_values(
                ["probability", "code"], ascending=[False, True])
            if cross.empty:
                continue
            count = max(1, math.ceil(len(cross) * fraction))
            chosen = cross.head(count).copy()
            target = {str(code): 1 / count for code in chosen["code"]}
            all_codes = set(weights) | set(target)
            buys = sum(max(target.get(code, 0) - weights.get(code, 0), 0) for code in all_codes)
            sells = sum(max(weights.get(code, 0) - target.get(code, 0), 0) for code in all_codes)
            cost_pct = (buys * (commission + slippage) +
                        sells * (commission + slippage + tax))
            gross = float(chosen["forward_return"].mean())
            benchmark = float(chosen["benchmark_forward_return"].mean())
            net = gross - cost_pct
            equity *= 1 + net / 100
            benchmark_equity *= 1 + benchmark / 100
            peak = max(peak, equity)
            mdd = min(mdd, equity / peak - 1)
            positive_periods += int(net > benchmark)
            periods += 1
            total_turnover += buys + sells
            total_cost += cost_pct
            for row in chosen.itertuples(index=False):
                holdings.append({
                    "scope": scope, "feature_date": day, "top_fraction": fraction,
                    "code": row.code, "industry": row.industry, "weight": 1 / count,
                    "probability": row.probability, "forward_return": row.forward_return,
                    "weighted_gross_contribution": row.forward_return / count,
                    "allocated_cost_pct": cost_pct / count,
                    "weighted_net_contribution": (row.forward_return - cost_pct) / count,
                    "benchmark_forward_return": row.benchmark_forward_return,
                })
            concentration.append({
                "scope": scope, "feature_date": day, "top_fraction": fraction,
                "holdings": count, "max_weight": 1 / count,
                "weight_hhi": count * (1 / count) ** 2,
                "top_industry_weight": chosen["industry"].value_counts().max() / count,
                "turnover": buys + sells, "estimated_cost_pct": cost_pct,
            })
            weights = target
        summaries.append({
            "scope": scope, "top_fraction": fraction, "periods": periods,
            "net_return": (equity - 1) * 100,
            "benchmark_return": (benchmark_equity - 1) * 100,
            "net_excess_return": (equity - benchmark_equity) * 100,
            "mdd": mdd * 100,
            "positive_period_rate": positive_periods / periods if periods else 0,
            "turnover": total_turnover, "total_cost_pct": total_cost,
        })
    return pd.DataFrame(summaries), pd.DataFrame(holdings), pd.DataFrame(concentration)


def _regime_rows(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in predictions.groupby(["split", "market_regime"], dropna=False):
        rows.append({
            "split": keys[0], "dimension": "market_trend", "regime": keys[1],
            "samples": len(group),
            "roc_auc": _safe_auc(group["positive_excess"], group["probability"]),
            "mean_excess_return": group["excess_return"].mean(),
            "mean_probability": group["probability"].mean(),
        })
    for split, split_frame in predictions.groupby("split"):
        daily = split_frame[["feature_date", "benchmark_volatility_60"]].drop_duplicates(
            "feature_date").sort_values("feature_date")
        if len(daily) < 3:
            continue
        daily["volatility_regime"] = pd.qcut(
            daily["benchmark_volatility_60"].rank(method="first"), 3,
            labels=["low", "medium", "high"])
        merged = split_frame.merge(
            daily[["feature_date", "volatility_regime"]], on="feature_date", how="left")
        for regime, group in merged.groupby("volatility_regime", observed=True):
            rows.append({
                "split": split, "dimension": "market_volatility", "regime": str(regime),
                "samples": len(group),
                "roc_auc": _safe_auc(group["positive_excess"], group["probability"]),
                "mean_excess_return": group["excess_return"].mean(),
                "mean_probability": group["probability"].mean(),
            })
    return pd.DataFrame(rows)


def _coefficient_rows(model, columns: list[str], feature_set: str,
                      missing_indicators: bool) -> pd.DataFrame:
    if not isinstance(model, Pipeline) or not isinstance(
            model.named_steps.get("model"), LogisticRegression):
        return pd.DataFrame()
    names = model.named_steps["imputer"].get_feature_names_out(columns)
    values = model.named_steps["model"].coef_[0]
    return pd.DataFrame({
        "feature_set": feature_set, "missing_indicators": missing_indicators,
        "feature": names.astype(str), "coefficient": values,
        "absolute_coefficient": np.abs(values),
    }).sort_values("absolute_coefficient", ascending=False)


def run_ml_diagnostics_v2(
        conn: sqlite3.Connection, horizon: int = 20, benchmark_code: str = "069500",
        validation_days: int = 126, test_days: int = 126, min_train_days: int = 504,
        fold_days: int = 126, commission: float = .015, tax: float = .18,
        slippage: float = .05, output_prefix: str = "ml_corrected_h20",
        lockbox_start: str | None = None, universe_history_csv: str | None = None,
        rank_scope: str = "market") -> dict:
    data = load_ml_dataset(conn, horizon, benchmark_code)
    if data.empty:
        raise ValueError("진단 데이터가 없습니다. build-feature-store를 먼저 실행하세요.")
    original_codes = set(data["code"].unique())
    history, history_verified, history_status = _read_universe_history(universe_history_csv)
    data, universe_audit = _apply_universe_history(data, history)
    covered = set(universe_audit.loc[
        universe_audit["history_status"] == "COVERED", "code"]) if not history.empty else set()
    universe_verified = bool(history_verified and original_codes <= covered)
    data = _rank_features(data, rank_scope)
    registered_lockbox, lockbox_registered = _registered_lockbox_start(
        conn, benchmark_code, horizon, lockbox_start)
    dates, validation_start, test_start, train, validation, lockbox = _split(
        data, validation_days, test_days, registered_lockbox)

    metrics, validation_predictions, fitted = [], [], {}
    candidates = [
        (model, feature_set, indicators)
        for model in ("logistic_regression", "hist_gradient_boosting")
        for feature_set in FEATURE_SETS
        for indicators in (False, True)
    ]
    for model_name, feature_set, indicators in candidates:
        columns = FEATURE_SETS[feature_set]
        metric, prediction, model = _fit_evaluate(
            train, validation, columns, "validation", "all", model_name,
            feature_set, indicators)
        metrics.append(metric); validation_predictions.append(prediction)
        fitted[(model_name, feature_set, indicators)] = model
    metrics_frame = pd.DataFrame(metrics)
    eligible = metrics_frame.sort_values(
        ["brier", "roc_auc", "missing_indicators"], ascending=[True, False, True])
    selected = eligible.iloc[0]
    selected_model = str(selected["model_name"])
    selected_features = str(selected["feature_set"])
    selected_indicators = bool(selected["missing_indicators"])
    columns = FEATURE_SETS[selected_features]

    development = data[(data["feature_date"] < test_start) &
                       (data["label_available_at"] < test_start)]
    lock_metric, lock_predictions, final_model = _fit_evaluate(
        development, lockbox, columns, "lockbox_test", "all", selected_model,
        selected_features, selected_indicators)
    metrics.append(lock_metric)
    metrics_frame = pd.DataFrame(metrics)

    # Walk-forward ends before validation begins; neither validation nor lockbox can leak in.
    development_dates = dates[dates < validation_start]
    walk_rows, walk_predictions = [], []
    fold = 0
    for offset in range(min_train_days, len(development_dates), fold_days):
        fold_dates = development_dates[offset:min(offset + fold_days, len(development_dates))]
        if len(fold_dates) < max(20, fold_days // 3):
            continue
        fold_start = fold_dates[0]
        fold_train = data[(data["feature_date"] < fold_start) &
                          (data["label_available_at"] < fold_start)]
        fold_test = data[data["feature_date"].isin(fold_dates)]
        if fold_train.empty or fold_test.empty:
            continue
        fold += 1
        metric, prediction, _ = _fit_evaluate(
            fold_train, fold_test, columns, f"walk_forward_{fold}", "all",
            selected_model, selected_features, selected_indicators)
        portfolio, _, _ = _portfolio(
            prediction, horizon, commission, tax, slippage, f"walk_forward_{fold}")
        top20 = portfolio[portfolio["top_fraction"] == .20].iloc[0]
        metric.update({
            "fold": fold, "train_start": fold_train["feature_date"].min(),
            "train_end": fold_train["feature_date"].max(),
            "test_start": fold_dates[0], "test_end": fold_dates[-1],
            "top20_net_excess_return": top20["net_excess_return"],
        })
        walk_rows.append(metric); walk_predictions.append(prediction.assign(fold=fold))
    walk_frame = pd.DataFrame(walk_rows)
    walk_prediction_frame = (pd.concat(walk_predictions, ignore_index=True)
                             if walk_predictions else pd.DataFrame())

    portfolio_frames, holding_frames, concentration_frames = [], [], []
    for scope, prediction in (("walk_forward_pre_validation", walk_prediction_frame),
                              ("lockbox_test", lock_predictions)):
        if prediction.empty:
            continue
        p, h, c = _portfolio(prediction, horizon, commission, tax, slippage, scope)
        portfolio_frames.append(p); holding_frames.append(h); concentration_frames.append(c)
    portfolios = pd.concat(portfolio_frames, ignore_index=True)
    holdings = pd.concat(holding_frames, ignore_index=True)
    concentration = pd.concat(concentration_frames, ignore_index=True)

    # Separate financial/non-financial diagnostic models. Bank-safe features intentionally
    # exclude revenue growth, operating margin, debt ratio, and operating cash flow.
    group_rows = []
    for group_name, is_financial in (("financial", True), ("non_financial", False)):
        group_train = train[(train["industry"] == "금융") == is_financial]
        group_validation = validation[(validation["industry"] == "금융") == is_financial]
        group_lockbox = lockbox[(lockbox["industry"] == "금융") == is_financial]
        group_columns = (PRICE_FEATURES + BANK_SAFE_FINANCIAL_FEATURES
                         if is_financial else FEATURE_COLUMNS)
        group_feature_set = "bank_safe" if is_financial else "nonfinancial_full"
        if min(len(group_train), len(group_validation), len(group_lockbox)) == 0:
            continue
        if group_train["positive_excess"].nunique() < 2:
            continue
        metric, _, _ = _fit_evaluate(
            group_train, group_validation, group_columns, "validation", group_name,
            "logistic_regression", group_feature_set, False)
        group_rows.append(metric)
        group_development = development[(development["industry"] == "금융") == is_financial]
        metric, _, _ = _fit_evaluate(
            group_development, group_lockbox, group_columns, "lockbox_test", group_name,
            "logistic_regression", group_feature_set, False)
        group_rows.append(metric)
    group_metrics = pd.DataFrame(group_rows)

    walk_independent = bool(walk_frame.empty or (
        walk_frame["test_end"].max() < validation_start and
        walk_frame["test_end"].max() < test_start))
    independence = pd.DataFrame([
        {"check": "walk_forward_before_validation", "passed": walk_independent,
         "latest_walk_test_end": None if walk_frame.empty else walk_frame["test_end"].max(),
         "validation_start": validation_start, "lockbox_start": test_start},
        {"check": "label_purge_at_boundaries", "passed": True,
         "latest_walk_test_end": None, "validation_start": validation_start,
         "lockbox_start": test_start},
        {"check": "immutable_lockbox_registered", "passed": lockbox_registered,
         "latest_walk_test_end": None, "validation_start": validation_start,
         "lockbox_start": test_start},
    ])
    walk_top20 = portfolios[(portfolios["scope"] == "walk_forward_pre_validation") &
                            (portfolios["top_fraction"] == .20)]
    lock_top20 = portfolios[(portfolios["scope"] == "lockbox_test") &
                            (portfolios["top_fraction"] == .20)]
    positive_fold_rate = (float((walk_frame["top20_net_excess_return"] > 0).mean())
                          if not walk_frame.empty else 0.0)
    criteria = {
        "independent_evaluation_periods": walk_independent,
        "immutable_lockbox_registered": lockbox_registered,
        "point_in_time_universe_verified": universe_verified,
        "dummy_brier_improved": bool(lock_metric["brier_skill_score"] > 0),
        "walk_forward_auc_above_random": bool(
            not walk_frame.empty and walk_frame["roc_auc"].dropna().mean() > .5),
        "cost_adjusted_top20_excess_positive": bool(
            not walk_top20.empty and walk_top20.iloc[0]["net_excess_return"] > 0),
        "majority_folds_cost_adjusted_excess_positive": bool(positive_fold_rate > .5),
        "lockbox_cost_adjusted_excess_positive": bool(
            not lock_top20.empty and lock_top20.iloc[0]["net_excess_return"] > 0),
    }
    verdict = "ADOPT" if all(criteria.values()) else "RESEARCH_ONLY"
    summary = {
        "version": 2, "verdict": verdict, "selected_model": selected_model,
        "selected_feature_set": selected_features,
        "selected_missing_indicators": selected_indicators,
        "rank_scope": rank_scope, "horizon": horizon,
        "validation_period": [validation["feature_date"].min(), validation["feature_date"].max()],
        "lockbox_period": [lockbox["feature_date"].min(), lockbox["feature_date"].max()],
        "walk_forward_period": [None if walk_frame.empty else walk_frame["test_start"].min(),
                                None if walk_frame.empty else walk_frame["test_end"].max()],
        "walk_forward_folds": int(len(walk_frame)),
        "universe_history_status": history_status,
        "criteria": criteria,
        "cost_assumptions_pct": {"commission_one_way": commission,
                                 "sell_tax": tax, "slippage_one_way": slippage},
        "safety": "RESEARCH_AND_SHADOW_ONLY_NO_LIVE_ORDERS",
    }
    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)

    def save(frame: pd.DataFrame, suffix: str):
        frame.to_csv(prefix.with_name(prefix.name + suffix), index=False, encoding="utf-8-sig")

    save(metrics_frame, "_metrics.csv")
    save(walk_frame, "_walk_forward.csv")
    save(portfolios, "_portfolios.csv")
    save(holdings, "_holding_contributions.csv")
    save(concentration, "_concentration.csv")
    save(group_metrics, "_financial_nonfinancial.csv")
    save(_regime_rows(pd.concat([walk_prediction_frame, lock_predictions], ignore_index=True)),
         "_market_regimes.csv")
    save(universe_audit, "_universe_audit.csv")
    save(independence, "_independence_audit.csv")
    save(_coefficient_rows(final_model, columns, selected_features, selected_indicators),
         "_feature_coefficients.csv")
    prefix.with_name(prefix.name + "_verdict.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
