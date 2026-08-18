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
