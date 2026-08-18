from __future__ import annotations

from dataclasses import asdict, dataclass
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

from src.ml.feature_store import ACCOUNT_RULES, FEATURE_COLUMNS
from src.ml.models import load_ml_dataset


PRICE_FEATURES = FEATURE_COLUMNS[:17]
FINANCIAL_FEATURES = FEATURE_COLUMNS[17:]
FEATURE_SETS = {
    "price_only": PRICE_FEATURES,
    "financial_only": FINANCIAL_FEATURES,
    "price_financial": FEATURE_COLUMNS,
}


@dataclass(frozen=True)
class DiagnosticMetric:
    split: str
    model_name: str
    feature_set: str
    sample_count: int
    positive_rate: float
    roc_auc: float | None
    accuracy: float
    brier: float
    dummy_brier: float
    brier_skill_score: float
    mean_excess_return: float


def _pipeline(model_name: str):
    if model_name == "dummy_prior":
        return DummyClassifier(strategy="prior")
    if model_name == "logistic_regression":
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(
                max_iter=2000, class_weight="balanced", random_state=42)),
        ])
    if model_name == "hist_gradient_boosting":
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("model", HistGradientBoostingClassifier(
                learning_rate=.05, max_iter=200, max_leaf_nodes=15,
                l2_regularization=1.0, random_state=42)),
        ])
    raise ValueError(f"지원하지 않는 모델입니다: {model_name}")


def _safe_auc(target, probabilities) -> float | None:
    return None if len(np.unique(target)) < 2 else float(roc_auc_score(target, probabilities))


def _evaluate(split: str, model_name: str, feature_set: str, frame: pd.DataFrame,
              probabilities: np.ndarray, dummy_probabilities: np.ndarray
              ) -> tuple[DiagnosticMetric, pd.DataFrame]:
    target = frame["positive_excess"].astype(int).to_numpy()
    brier = float(brier_score_loss(target, probabilities))
    dummy_brier = float(brier_score_loss(target, dummy_probabilities))
    metric = DiagnosticMetric(
        split=split, model_name=model_name, feature_set=feature_set,
        sample_count=len(frame), positive_rate=float(target.mean()),
        roc_auc=_safe_auc(target, probabilities),
        accuracy=float(accuracy_score(target, probabilities >= .5)), brier=brier,
        dummy_brier=dummy_brier,
        brier_skill_score=(1 - brier / dummy_brier) if dummy_brier else 0.0,
        mean_excess_return=float(frame["excess_return"].mean()),
    )
    output = frame[["code", "feature_date", "industry", "positive_excess",
                    "forward_return", "benchmark_forward_return", "excess_return",
                    "max_drawdown"]].copy()
    output["split"] = split
    output["model_name"] = model_name
    output["feature_set"] = feature_set
    output["probability"] = probabilities
    return metric, output


def _split_dates(data: pd.DataFrame, validation_days: int, test_days: int):
    dates = np.array(sorted(data["feature_date"].unique()))
    if len(dates) < validation_days + test_days + 252:
        raise ValueError("ML 진단에 필요한 거래일이 부족합니다.")
    validation_start = dates[-(validation_days + test_days)]
    test_start = dates[-test_days]
    train = data[(data["feature_date"] < validation_start) &
                 (data["label_available_at"] < validation_start)]
    validation = data[(data["feature_date"] >= validation_start) &
                      (data["feature_date"] < test_start) &
                      (data["label_available_at"] < test_start)]
    lockbox = data[data["feature_date"] >= test_start]
    return train, validation, lockbox


def _calibration_rows(predictions: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    rows = []
    for keys, group in predictions.groupby(["split", "model_name", "feature_set"]):
        bucket = pd.cut(group["probability"], np.linspace(0, 1, bins + 1),
                        include_lowest=True, labels=False)
        for number, part in group.groupby(bucket, observed=True):
            rows.append({"split": keys[0], "model_name": keys[1],
                         "feature_set": keys[2], "bin": int(number) + 1,
                         "count": len(part),
                         "mean_probability": part["probability"].mean(),
                         "actual_positive_rate": part["positive_excess"].mean()})
    return pd.DataFrame(rows)


def _coefficient_rows(model, columns: list[str], feature_set: str) -> list[dict]:
    if not isinstance(model, Pipeline) or "model" not in model.named_steps:
        return []
    estimator = model.named_steps["model"]
    if not isinstance(estimator, LogisticRegression):
        return []
    names = model.named_steps["imputer"].get_feature_names_out(columns)
    return [{"feature_set": feature_set, "feature": str(name),
             "coefficient": float(value), "absolute_coefficient": abs(float(value))}
            for name, value in zip(names, estimator.coef_[0])]


def _portfolio_backtest(predictions: pd.DataFrame, horizon: int,
                        commission: float, tax: float, slippage: float) -> pd.DataFrame:
    """Non-overlapping, equal-weight top-bucket portfolios with explicit costs."""
    rows = []
    for (model_name, feature_set), model_data in predictions.groupby(
            ["model_name", "feature_set"]):
        dates = sorted(model_data["feature_date"].unique())[::horizon]
        for fraction in (.10, .20, .30):
            weights: dict[str, float] = {}
            equity = benchmark_equity = 1.0
            peak = 1.0
            mdd = 0.0
            positive_periods = periods = 0
            total_turnover = total_cost = 0.0
            period_excesses = []
            for day in dates:
                cross = model_data[model_data["feature_date"] == day].sort_values(
                    "probability", ascending=False)
                if cross.empty:
                    continue
                count = max(1, math.ceil(len(cross) * fraction))
                chosen = cross.head(count)
                target = {str(code): 1 / count for code in chosen["code"]}
                all_codes = set(weights) | set(target)
                buys = sum(max(target.get(code, 0) - weights.get(code, 0), 0)
                           for code in all_codes)
                sells = sum(max(weights.get(code, 0) - target.get(code, 0), 0)
                            for code in all_codes)
                cost_pct = (buys * (commission + slippage) +
                            sells * (commission + slippage + tax))
                gross = float(chosen["forward_return"].mean())
                benchmark = float(chosen["benchmark_forward_return"].mean())
                net = gross - cost_pct
                equity *= 1 + net / 100
                benchmark_equity *= 1 + benchmark / 100
                peak = max(peak, equity)
                mdd = min(mdd, equity / peak - 1)
                period_excesses.append(net - benchmark)
                positive_periods += int(net > benchmark)
                periods += 1
                total_turnover += buys + sells
                total_cost += cost_pct
                weights = target
            rows.append({
                "model_name": model_name, "feature_set": feature_set,
                "top_fraction": fraction, "periods": periods,
                "net_return": (equity - 1) * 100,
                "benchmark_return": (benchmark_equity - 1) * 100,
                "net_excess_return": (equity - benchmark_equity) * 100,
                "mdd": mdd * 100,
                "positive_period_rate": positive_periods / periods if periods else 0,
                "average_period_excess": float(np.mean(period_excesses)) if periods else np.nan,
                "turnover": total_turnover, "total_cost_pct": total_cost,
            })
    return pd.DataFrame(rows)


def financial_missingness_reports(conn: sqlite3.Connection, codes: list[str],
                                  start_year: int = 2021, end_year: int = 2025
                                  ) -> tuple[pd.DataFrame, pd.DataFrame]:
    item_rows = []
    for code in codes:
        for year in range(start_year, end_year + 1):
            available = pd.read_sql_query(
                """SELECT fs_div,sj_div,account_id,account_name,amount,disclosed_at
                   FROM financial_statements WHERE code=? AND fiscal_year=?
                     AND report_code='11011' AND fs_div IN ('CFS','OFS')""",
                conn, params=(code, year))
            source = ("CFS" if not available[available["fs_div"] == "CFS"].empty
                      else "OFS" if not available[available["fs_div"] == "OFS"].empty else None)
            selected = available[available["fs_div"] == source] if source else available
            normalized_ids = set(selected["account_id"].astype(str))
            normalized_names = set(selected["account_name"].astype(str).str.replace(" ", ""))
            for item, (ids, names, statements) in ACCOUNT_RULES.items():
                found = (bool(normalized_ids.intersection(ids)) or
                         bool(normalized_names.intersection(name.replace(" ", "") for name in names)))
                item_rows.append({"code": code, "fiscal_year": year,
                                  "financial_source": source or "MISSING",
                                  "account_item": item, "available": int(found),
                                  "missing": int(not found),
                                  "disclosed_at": (selected["disclosed_at"].dropna().min()
                                                   if not selected.empty else None)})
    items = pd.DataFrame(item_rows)
    feature_rows = []
    for code in codes:
        frame = pd.read_sql_query(
            f"SELECT {','.join(FEATURE_COLUMNS)} FROM ml_features WHERE code=?", conn,
            params=(code,))
        for column in FEATURE_COLUMNS:
            feature_rows.append({"code": code, "feature": column,
                                 "rows": len(frame),
                                 "missing_rows": int(frame[column].isna().sum()) if not frame.empty else 0,
                                 "missing_rate": float(frame[column].isna().mean()) if not frame.empty else 1.0})
    return items, pd.DataFrame(feature_rows)


def _shadow_summary(conn: sqlite3.Connection, portfolio_id: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """SELECT performance_date,equity,cumulative_return,benchmark_return
           FROM shadow_book_performance WHERE portfolio_id=? ORDER BY performance_date""",
        conn, params=(portfolio_id,))
    if frame.empty:
        return pd.DataFrame([{"portfolio_id": portfolio_id, "trading_days": 0,
                              "status": "NO_DATA"}])
    latest = frame.iloc[-1]
    return pd.DataFrame([{
        "portfolio_id": portfolio_id, "trading_days": len(frame),
        "start_date": frame.iloc[0]["performance_date"],
        "end_date": latest["performance_date"],
        "strategy_return": float(latest["cumulative_return"]) * 100,
        "benchmark_return": float(latest["benchmark_return"]) * 100,
        "excess_return": (float(latest["cumulative_return"]) -
                          float(latest["benchmark_return"])) * 100,
        "status": "COMPARABLE" if len(frame) >= 120 else "OBSERVATION_ONLY",
    }])


def run_ml_diagnostics(conn: sqlite3.Connection, horizon: int = 20,
                       benchmark_code: str = "069500", validation_days: int = 126,
                       test_days: int = 126, min_train_days: int = 504,
                       fold_days: int = 126, commission: float = .015,
                       tax: float = .18, slippage: float = .05,
                       portfolio_id: str = "shadow_24_filtered",
                       output_prefix: str = "ml_diagnostic_h20") -> dict:
    data = load_ml_dataset(conn, horizon, benchmark_code)
    if data.empty:
        raise ValueError("진단 데이터가 없습니다. build-feature-store를 먼저 실행하세요.")
    train, validation, lockbox = _split_dates(data, validation_days, test_days)
    models = ("dummy_prior", "logistic_regression", "hist_gradient_boosting")
    metrics: list[dict] = []
    predictions: list[pd.DataFrame] = []
    fitted: dict[tuple[str, str], object] = {}
    coefficients = []
    for feature_set, columns in FEATURE_SETS.items():
        dummy = _pipeline("dummy_prior").fit(train[columns], train["positive_excess"])
        dummy_val = dummy.predict_proba(validation[columns])[:, 1]
        dummy_test = _pipeline("dummy_prior").fit(
            pd.concat([train, validation])[columns],
            pd.concat([train, validation])["positive_excess"]).predict_proba(lockbox[columns])[:, 1]
        for model_name in models:
            model = _pipeline(model_name)
            model.fit(train[columns], train["positive_excess"].astype(int))
            val_probs = model.predict_proba(validation[columns])[:, 1]
            metric, output = _evaluate("validation", model_name, feature_set,
                                       validation, val_probs, dummy_val)
            metrics.append(asdict(metric)); predictions.append(output)
            development = pd.concat([train, validation], ignore_index=True)
            final = _pipeline(model_name).fit(
                development[columns], development["positive_excess"].astype(int))
            test_probs = final.predict_proba(lockbox[columns])[:, 1]
            metric, output = _evaluate("lockbox_test", model_name, feature_set,
                                       lockbox, test_probs, dummy_test)
            metrics.append(asdict(metric)); predictions.append(output)
            fitted[(model_name, feature_set)] = final
            coefficients.extend(_coefficient_rows(final, columns, feature_set))
    metrics_frame = pd.DataFrame(metrics)
    predictions_frame = pd.concat(predictions, ignore_index=True)
    eligible = metrics_frame[(metrics_frame["split"] == "validation") &
                             (metrics_frame["model_name"] != "dummy_prior")]
    selected_row = eligible.sort_values(["brier", "roc_auc"], ascending=[True, False]).iloc[0]
    selected_model = str(selected_row["model_name"])
    selected_features = str(selected_row["feature_set"])

    # Expanding walk-forward with label purge at every fold boundary.
    dates = np.array(sorted(data["feature_date"].unique()))
    walk_metrics = []
    walk_predictions = []
    fold = 0
    for offset in range(min_train_days, len(dates), fold_days):
        test_dates = dates[offset:min(offset + fold_days, len(dates))]
        if len(test_dates) < max(20, fold_days // 3):
            continue
        test_start = test_dates[0]
        fold_train = data[(data["feature_date"] < test_start) &
                          (data["label_available_at"] < test_start)]
        fold_test = data[data["feature_date"].isin(test_dates)]
        if fold_train.empty or fold_test.empty:
            continue
        fold += 1
        columns = FEATURE_SETS[selected_features]
        dummy = _pipeline("dummy_prior")
        dummy.fit(fold_train[columns], fold_train["positive_excess"])
        dummy_probs = dummy.predict_proba(fold_test[columns])[:, 1]
        model = _pipeline(selected_model).fit(
            fold_train[columns], fold_train["positive_excess"].astype(int))
        probabilities = model.predict_proba(fold_test[columns])[:, 1]
        metric, output = _evaluate(f"walk_forward_{fold}", selected_model,
                                   selected_features, fold_test, probabilities, dummy_probs)
        row = asdict(metric)
        fold_portfolio = _portfolio_backtest(
            output, horizon, commission, tax, slippage)
        fold_top20 = fold_portfolio[fold_portfolio["top_fraction"] == .20].iloc[0]
        row.update({"fold": fold, "train_start": fold_train["feature_date"].min(),
                    "train_end": fold_train["feature_date"].max(),
                    "test_start": test_dates[0], "test_end": test_dates[-1],
                    "top20_net_return": fold_top20["net_return"],
                    "top20_benchmark_return": fold_top20["benchmark_return"],
                    "top20_net_excess_return": fold_top20["net_excess_return"]})
        walk_metrics.append(row)
        walk_predictions.append(output.assign(fold=fold))
    walk_metrics_frame = pd.DataFrame(walk_metrics)
    walk_predictions_frame = (pd.concat(walk_predictions, ignore_index=True)
                              if walk_predictions else pd.DataFrame())
    lockbox_selected = predictions_frame[
        (predictions_frame["split"] == "lockbox_test") &
        (predictions_frame["model_name"] == selected_model) &
        (predictions_frame["feature_set"] == selected_features)]
    walk_portfolios = _portfolio_backtest(
        walk_predictions_frame, horizon, commission, tax, slippage).assign(scope="walk_forward")
    lockbox_portfolios = _portfolio_backtest(
        lockbox_selected, horizon, commission, tax, slippage).assign(scope="lockbox_test")
    portfolios = pd.concat([walk_portfolios, lockbox_portfolios], ignore_index=True)
    selected_portfolio = portfolios[(portfolios["scope"] == "walk_forward") &
                                    (portfolios["top_fraction"] == .20)].iloc[0]
    lockbox_portfolio = portfolios[(portfolios["scope"] == "lockbox_test") &
                                   (portfolios["top_fraction"] == .20)].iloc[0]

    by_year = []
    evaluation_frame = (walk_predictions_frame if not walk_predictions_frame.empty
                        else lockbox_selected)
    for year, group in evaluation_frame.groupby(evaluation_frame["feature_date"].str[:4]):
        by_year.append({"year": year, "samples": len(group),
                        "roc_auc": _safe_auc(group["positive_excess"], group["probability"]),
                        "mean_excess_return": group["excess_return"].mean()})
    by_industry = []
    for industry, group in evaluation_frame.groupby("industry"):
        by_industry.append({"industry": industry, "samples": len(group),
                            "roc_auc": _safe_auc(group["positive_excess"], group["probability"]),
                            "mean_excess_return": group["excess_return"].mean()})

    selected_test = metrics_frame[(metrics_frame["split"] == "lockbox_test") &
                                  (metrics_frame["model_name"] == selected_model) &
                                  (metrics_frame["feature_set"] == selected_features)].iloc[0]
    positive_fold_rate = (float((walk_metrics_frame["top20_net_excess_return"] > 0).mean())
                          if not walk_metrics_frame.empty else 0.0)
    criteria = {
        "dummy_brier_improved": bool(selected_test["brier_skill_score"] > 0),
        "walk_forward_auc_above_random": bool(
            not walk_metrics_frame.empty and walk_metrics_frame["roc_auc"].mean() > .5),
        "cost_adjusted_top20_excess_positive": bool(selected_portfolio["net_excess_return"] > 0),
        "majority_folds_cost_adjusted_excess_positive": bool(positive_fold_rate > .5),
        "lockbox_cost_adjusted_excess_positive": bool(lockbox_portfolio["net_excess_return"] > 0),
    }
    verdict = "ADOPT" if all(criteria.values()) else "RESEARCH_ONLY"
    summary = {
        "verdict": verdict, "selected_model": selected_model,
        "selected_feature_set": selected_features, "horizon": horizon,
        "validation_period": [validation["feature_date"].min(), validation["feature_date"].max()],
        "lockbox_period": [lockbox["feature_date"].min(), lockbox["feature_date"].max()],
        "walk_forward_folds": int(len(walk_metrics_frame)),
        "criteria": criteria,
        "cost_assumptions_pct": {"commission_one_way": commission,
                                 "sell_tax": tax, "slippage_one_way": slippage},
    }
    prefix = Path(output_prefix)
    def save(frame: pd.DataFrame, suffix: str):
        frame.to_csv(prefix.with_name(prefix.name + suffix), index=False, encoding="utf-8-sig")
    save(metrics_frame, "_metrics.csv")
    save(walk_metrics_frame, "_walk_forward.csv")
    save(portfolios, "_portfolios.csv")
    save(_calibration_rows(predictions_frame), "_calibration.csv")
    save(pd.DataFrame(coefficients).sort_values("absolute_coefficient", ascending=False),
         "_feature_coefficients.csv")
    save(pd.DataFrame(by_year), "_by_year.csv")
    save(pd.DataFrame(by_industry), "_by_industry.csv")
    save(_shadow_summary(conn, portfolio_id), "_shadow_comparison.csv")
    prefix.with_name(prefix.name + "_verdict.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
