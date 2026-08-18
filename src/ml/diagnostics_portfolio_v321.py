from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from src.ml.diagnostics_features_v321 import FINANCIAL_FEATURES, PRICE_FEATURES, _rank_features, _split
from src.ml.diagnostics_research_v321 import (
    Candidate, _apply_universe_history, _bank_safe, _daily_ic, _estimator,
    _factor_score, _fit_predict, _read_universe_history,
    _registered_lockbox_start, _research_cutoff_and_lockbox_novelty,
    _target,
)
from src.ml.models import load_ml_dataset


TOTAL_RETURN_COLUMNS = {"code", "date", "total_return_index", "known_at", "source"}
SECURITY_MASTER_COLUMNS = {"code", "name"}
EVENT_FINANCIAL_FEATURES = [
    "revenue_growth", "operating_margin", "roe", "debt_ratio",
    "operating_cash_flow_positive", "reported_eps", "estimated_bps",
]


@dataclass(frozen=True)
class EnsembleCandidate:
    model_name: str
    target_kind: str
    financial_weight: float | None

    @property
    def feature_set(self) -> str:
        return "regime_dynamic" if self.financial_weight is None else (
            f"financial_{self.financial_weight:.2f}_momentum_{1-self.financial_weight:.2f}")


@dataclass(frozen=True)
class EventCandidate:
    model_name: str
    target_kind: str

    @property
    def feature_set(self) -> str:
        return "financial_event_only"


def _normalise_date(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("-", "", regex=False).str.strip()


def _read_total_return_history(path: str | None) -> tuple[pd.DataFrame, bool, str]:
    if not path:
        return pd.DataFrame(), False, "RAW_CLOSE_ONLY"
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = TOTAL_RETURN_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("총수익지수 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    frame["date"] = _normalise_date(frame["date"])
    frame["known_at"] = _normalise_date(frame["known_at"])
    frame["total_return_index"] = pd.to_numeric(frame["total_return_index"], errors="coerce")
    invalid = (
        frame["date"].str.len().ne(8)
        | frame["known_at"].str.len().ne(8)
        | frame["known_at"].gt(frame["date"])
        | frame["total_return_index"].isna()
        | frame["total_return_index"].le(0)
        | frame["source"].str.strip().eq("")
        | frame.duplicated(["code", "date"], keep=False)
    )
    verified = bool(not frame.empty and not invalid.any())
    return frame, verified, "VERIFIED_TOTAL_RETURN_INPUT" if verified else "INVALID_TOTAL_RETURN_INPUT"


def _read_security_master(path: str | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame(columns=["code", "name"])
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = SECURITY_MASTER_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("종목명 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    if frame["code"].duplicated().any():
        raise ValueError("종목명 CSV에 중복 코드가 있습니다.")
    return frame[["code", "name"]]


def _apply_total_return_labels(data: pd.DataFrame, history: pd.DataFrame,
                               input_valid: bool, benchmark_code: str
                               ) -> tuple[pd.DataFrame, bool, float]:
    """Replace raw-close labels only when every required total-return endpoint exists."""
    if history.empty or data.empty or not input_valid:
        return data.copy(), False, 0.0
    entry = history[["code", "date", "total_return_index"]].rename(
        columns={"date": "feature_date", "total_return_index": "tr_entry"})
    exit_frame = history[["code", "date", "total_return_index"]].rename(
        columns={"date": "label_available_at", "total_return_index": "tr_exit"})
    result = data.merge(entry, on=["code", "feature_date"], how="left").merge(
        exit_frame, on=["code", "label_available_at"], how="left")
    benchmark = history[history["code"] == benchmark_code]
    b_entry = benchmark[["date", "total_return_index"]].rename(
        columns={"date": "feature_date", "total_return_index": "benchmark_tr_entry"})
    b_exit = benchmark[["date", "total_return_index"]].rename(
        columns={"date": "label_available_at", "total_return_index": "benchmark_tr_exit"})
    result = result.merge(b_entry, on="feature_date", how="left").merge(
        b_exit, on="label_available_at", how="left")
    endpoints = ["tr_entry", "tr_exit", "benchmark_tr_entry", "benchmark_tr_exit"]
    coverage = result[endpoints].notna().all(axis=1)
    coverage_rate = float(coverage.mean()) if len(result) else 0.0
    if coverage_rate < .999:
        return data.copy(), False, coverage_rate
    result["raw_close_forward_return"] = result["forward_return"]
    result["raw_close_benchmark_forward_return"] = result["benchmark_forward_return"]
    result["forward_return"] = (result["tr_exit"] / result["tr_entry"] - 1) * 100
    result["benchmark_forward_return"] = (
        result["benchmark_tr_exit"] / result["benchmark_tr_entry"] - 1) * 100
    result["excess_return"] = result["forward_return"] - result["benchmark_forward_return"]
    result["positive_excess"] = result["excess_return"].gt(0).astype(int)
    return result, True, coverage_rate


def _cross_sectional_percentile(values: pd.Series, dates: pd.Series) -> np.ndarray:
    return values.groupby(dates).rank(method="average", pct=True).fillna(.5).to_numpy()


def _fit_predict_ensemble(candidate: EnsembleCandidate, train: pd.DataFrame,
                          test: pd.DataFrame) -> np.ndarray:
    financial = Candidate(candidate.model_name, candidate.target_kind, "financial_safe")
    momentum = Candidate(candidate.model_name, candidate.target_kind, "price_only")
    financial_score, _ = _fit_predict(financial, train, test)
    momentum_score, _ = _fit_predict(momentum, train, test)
    financial_rank = _cross_sectional_percentile(
        pd.Series(financial_score, index=test.index), test["feature_date"])
    momentum_rank = _cross_sectional_percentile(
        pd.Series(momentum_score, index=test.index), test["feature_date"])
    if candidate.financial_weight is not None:
        weights = np.full(len(test), candidate.financial_weight)
    else:
        regime = pd.to_numeric(test["market_regime"], errors="coerce").fillna(0).to_numpy()
        # 상승장에서는 모멘텀, 하락·횡보장에서는 재무 품질의 비중을 높인다.
        weights = np.where(regime > 0, .30, np.where(regime < 0, .65, .50))
    return financial_rank * weights + momentum_rank * (1 - weights)


def _candidate_scores(candidate: Candidate | EnsembleCandidate | EventCandidate,
                      train: pd.DataFrame,
                      test: pd.DataFrame) -> np.ndarray:
    if isinstance(candidate, EnsembleCandidate):
        return _fit_predict_ensemble(candidate, train, test)
    if isinstance(candidate, EventCandidate):
        model = _estimator(candidate.model_name)
        model.fit(train[EVENT_FINANCIAL_FEATURES], _target(train, candidate.target_kind))
        return np.asarray(model.predict(test[EVENT_FINANCIAL_FEATURES]), dtype=float)
    return _fit_predict(candidate, train, test)[0]


def _ic_rows(prediction: pd.DataFrame, horizon: int) -> pd.DataFrame:
    rows: list[dict] = []
    for day, group in prediction.groupby("feature_date", sort=True):
        ic = None
        if group["score"].nunique() > 1 and group["excess_return"].nunique() > 1:
            ic = float(group["score"].rank().corr(group["excess_return"].rank()))
        rows.append({"feature_date": day, "rank_ic": ic})
    result = pd.DataFrame(rows)
    if result.empty:
        result["non_overlapping"] = pd.Series(dtype=bool)
    else:
        result["non_overlapping"] = False
        result.loc[result.index[::horizon], "non_overlapping"] = True
    return result


def _bootstrap_mean_ci(values: pd.Series, seed: int = 42,
                       simulations: int = 2000) -> tuple[float | None, float | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(clean) < 2:
        return None, None
    rng = np.random.default_rng(seed)
    means = rng.choice(clean, size=(simulations, len(clean)), replace=True).mean(axis=1)
    low, high = np.quantile(means, [.025, .975])
    return float(low), float(high)


def _portfolio(predictions: pd.DataFrame, horizon: int, commission: float,
               tax: float, slippage: float, scope: str
               ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summaries: list[dict] = []
    holdings: list[dict] = []
    periods: list[dict] = []
    transitions: list[dict] = []
    dates = sorted(predictions["feature_date"].unique())[::horizon]
    for fraction in (.10, .20, .30):
        weights: dict[str, float] = {}
        model_equity = universe_equity = etf_equity = 1.0
        wins_universe = wins_etf = total_turnover = total_cost = 0.0
        previous: set[str] = set()
        for day in dates:
            cross = predictions[predictions["feature_date"] == day].sort_values(
                ["score", "code"], ascending=[False, True])
            if cross.empty:
                continue
            count = max(1, math.ceil(len(cross) * fraction))
            selected = cross.head(count).copy()
            current = set(selected["code"].astype(str))
            by_code = cross.set_index(cross["code"].astype(str), drop=False)
            cutoff_score = float(selected["score"].min())
            target = {code: 1 / count for code in current}
            codes = set(weights) | set(target)
            buys = sum(max(target.get(c, 0) - weights.get(c, 0), 0) for c in codes)
            sells = sum(max(weights.get(c, 0) - target.get(c, 0), 0) for c in codes)
            cost = buys * (commission + slippage) + sells * (commission + slippage + tax)
            gross = float(selected["forward_return"].mean())
            universe_return = float(cross["forward_return"].mean())
            etf_return = float(cross["benchmark_forward_return"].mean())
            net = gross - cost
            model_equity *= 1 + net / 100
            universe_equity *= 1 + universe_return / 100
            etf_equity *= 1 + etf_return / 100
            wins_universe += int(net > universe_return)
            wins_etf += int(net > etf_return)
            total_turnover += buys + sells
            total_cost += cost
            periods.append({
                "scope": scope, "feature_date": day, "top_fraction": fraction,
                "eligible_count": len(cross), "selected_count": count,
                "gross_return": gross, "net_return": net,
                "universe_equal_weight_return": universe_return, "etf_return": etf_return,
                "universe_excess_return": net - universe_return,
                "etf_excess_return": net - etf_return,
                "turnover": buys + sells, "cost_pct": cost,
            })
            for row in selected.itertuples(index=False):
                code = str(row.code)
                holdings.append({
                    "scope": scope, "feature_date": day, "top_fraction": fraction,
                    "code": code, "name": getattr(row, "name", ""),
                    "industry": row.industry, "position_status": "HELD" if code in previous else "NEW",
                    "weight": 1 / count, "score": row.score,
                    "entry_close": getattr(row, "close", np.nan),
                    "forward_return": row.forward_return,
                    "weighted_gross_contribution": row.forward_return / count,
                    "allocated_cost_pct": cost / count,
                    "weighted_net_contribution": (row.forward_return - cost) / count,
                })
            for code in sorted(previous - current):
                row = by_code.loc[code]
                transitions.append({"scope": scope, "feature_date": day,
                                    "top_fraction": fraction, "code": code,
                                    "name": row.get("name", ""),
                                    "industry": row.get("industry", ""),
                                    "score": row["score"], "cutoff_score": cutoff_score,
                                    "transition": "REMOVED", "reason": "SCORE_BELOW_CUTOFF"})
            for code in sorted(current - previous):
                row = by_code.loc[code]
                transitions.append({"scope": scope, "feature_date": day,
                                    "top_fraction": fraction, "code": code,
                                    "name": row.get("name", ""),
                                    "industry": row.get("industry", ""),
                                    "score": row["score"], "cutoff_score": cutoff_score,
                                    "transition": "ADDED", "reason": "SCORE_ABOVE_CUTOFF"})
            previous, weights = current, target
        n = len(dates)
        summaries.append({
            "scope": scope, "top_fraction": fraction, "periods": n,
            "net_return": (model_equity - 1) * 100,
            "universe_equal_weight_return": (universe_equity - 1) * 100,
            "etf_return": (etf_equity - 1) * 100,
            "universe_net_excess_return": (model_equity - universe_equity) * 100,
            "etf_net_excess_return": (model_equity - etf_equity) * 100,
            "positive_vs_universe_rate": wins_universe / n if n else 0,
            "positive_vs_etf_rate": wins_etf / n if n else 0,
            "turnover": total_turnover, "total_cost_pct": total_cost,
        })
    return (pd.DataFrame(summaries), pd.DataFrame(holdings),
            pd.DataFrame(periods), pd.DataFrame(transitions))


def _evaluate(candidate: Candidate | EnsembleCandidate | EventCandidate,
              train: pd.DataFrame,
              test: pd.DataFrame, horizon: int, commission: float, tax: float,
              slippage: float, split: str) -> tuple[dict, pd.DataFrame]:
    prediction = test.copy()
    prediction["score"] = _candidate_scores(candidate, train, test)
    daily_ic, positive_ic_rate = _daily_ic(prediction)
    ic = _ic_rows(prediction, horizon)
    non_overlap = ic[ic["non_overlapping"]]["rank_ic"]
    ci_low, ci_high = _bootstrap_mean_ci(non_overlap)
    portfolio, _, _, _ = _portfolio(
        prediction, horizon, commission, tax, slippage, split)
    top20 = portfolio[portfolio["top_fraction"] == .20].iloc[0]
    return {
        "split": split, "model_name": candidate.model_name,
        "target_kind": candidate.target_kind, "feature_set": candidate.feature_set,
        "samples": len(test), "daily_rank_ic": daily_ic,
        "positive_daily_ic_rate": positive_ic_rate,
        "nonoverlap_rank_ic": float(non_overlap.mean()) if non_overlap.notna().any() else None,
        "nonoverlap_ic_positive_rate": float((non_overlap.dropna() > 0).mean())
        if non_overlap.notna().any() else 0.0,
        "nonoverlap_ic_ci_low": ci_low, "nonoverlap_ic_ci_high": ci_high,
        "independent_ic_periods": int(non_overlap.notna().sum()),
        "top20_universe_net_excess_return": float(top20["universe_net_excess_return"]),
        "top20_etf_net_excess_return": float(top20["etf_net_excess_return"]),
        "top20_positive_vs_universe_rate": float(top20["positive_vs_universe_rate"]),
        "top20_positive_vs_etf_rate": float(top20["positive_vs_etf_rate"]),
    }, prediction


def _selection_score(metrics: pd.DataFrame) -> pd.Series:
    values = metrics.copy()
    columns = {
        "nonoverlap_rank_ic": .30,
        "nonoverlap_ic_ci_low": .20,
        "top20_universe_net_excess_return": .25,
        "top20_etf_net_excess_return": .15,
        "top20_positive_vs_universe_rate": .10,
    }
    score = pd.Series(0.0, index=values.index)
    for column, weight in columns.items():
        numeric = pd.to_numeric(values[column], errors="coerce").fillna(-999)
        score += numeric.rank(pct=True) * weight
    return score


def _total_return_audit(data: pd.DataFrame, history: pd.DataFrame,
                        input_valid: bool, benchmark_code: str,
                        horizon: int) -> tuple[pd.DataFrame, dict]:
    dates = sorted(data["feature_date"].unique())[::horizon]
    sampled = data[data["feature_date"].isin(dates)].copy()
    if history.empty or sampled.empty:
        return pd.DataFrame(), {
            "status": "TOTAL_RETURN_INPUT_NOT_AVAILABLE", "rows": int(len(sampled)),
            "coverage_rate": 0.0, "return_match_rate": 0.0,
            "total_return_verified": False,
        }
    entry = history.rename(columns={"date": "feature_date", "total_return_index": "tr_entry"})
    exit_frame = history.rename(columns={"date": "label_available_at",
                                          "total_return_index": "tr_exit"})
    audit = sampled.merge(entry[["code", "feature_date", "tr_entry", "source"]],
                          on=["code", "feature_date"], how="left")
    audit = audit.merge(exit_frame[["code", "label_available_at", "tr_exit"]],
                        on=["code", "label_available_at"], how="left")
    benchmark = history[history["code"] == benchmark_code]
    b_entry = benchmark[["date", "total_return_index"]].rename(
        columns={"date": "feature_date", "total_return_index": "benchmark_tr_entry"})
    b_exit = benchmark[["date", "total_return_index"]].rename(
        columns={"date": "label_available_at", "total_return_index": "benchmark_tr_exit"})
    audit = audit.merge(b_entry, on="feature_date", how="left").merge(
        b_exit, on="label_available_at", how="left")
    audit["total_return"] = (audit["tr_exit"] / audit["tr_entry"] - 1) * 100
    audit["benchmark_total_return"] = (
        audit["benchmark_tr_exit"] / audit["benchmark_tr_entry"] - 1) * 100
    audit["price_label_difference"] = audit["total_return"] - audit["forward_return"]
    audit["benchmark_label_difference"] = (
        audit["benchmark_total_return"] - audit["benchmark_forward_return"])
    coverage = audit[["tr_entry", "tr_exit", "benchmark_tr_entry",
                      "benchmark_tr_exit"]].notna().all(axis=1)
    comparable = audit[coverage]
    # 기존 라벨과의 차이는 배당·기업행사 조정이 정상이라면 0이 아닐 수도 있다.
    coverage_rate = float(coverage.mean()) if len(audit) else 0.0
    verified = bool(input_valid and coverage_rate >= .999)
    summary = {
        "status": "TOTAL_RETURN_VERIFIED" if verified else "TOTAL_RETURN_COVERAGE_INCOMPLETE",
        "rows": int(len(audit)), "comparable_rows": int(len(comparable)),
        "coverage_rate": coverage_rate,
        "return_match_rate": float((comparable["price_label_difference"].abs() <= 1e-8).mean())
        if len(comparable) else 0.0,
        "total_return_verified": verified,
    }
    return audit, summary


def _concentration(holdings: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if holdings.empty:
        return pd.DataFrame(), pd.DataFrame()
    rows: list[dict] = []
    warnings: list[dict] = []
    for (scope, fraction), group in holdings.groupby(["scope", "top_fraction"]):
        dates = int(group["feature_date"].nunique())
        counts = group.groupby(["code", "name"], dropna=False).size().reset_index(name="periods_held")
        losses = group[group["weighted_net_contribution"] < 0].groupby("code").size()
        contribution = group.groupby("code")["weighted_net_contribution"].sum()
        worst = group.groupby("code")["weighted_net_contribution"].min()
        for row in counts.itertuples(index=False):
            held_rate = row.periods_held / dates if dates else 0.0
            loss_periods = int(losses.get(row.code, 0))
            total_contribution = float(contribution.get(row.code, 0.0))
            record = {
                "scope": scope, "top_fraction": fraction, "code": row.code,
                "name": row.name, "periods_held": row.periods_held,
                "total_periods": dates, "held_rate": held_rate,
                "loss_periods": loss_periods, "net_contribution": total_contribution,
                "worst_period_contribution": float(worst.get(row.code, 0.0)),
            }
            rows.append(record)
            if held_rate >= .80:
                warnings.append({**record, "warning": "LONG_TERM_FIXED_HOLDING"})
            if loss_periods >= 2 and total_contribution < 0:
                warnings.append({**record, "warning": "REPEATED_LOSS"})
    warning_columns = [*pd.DataFrame(rows).columns, "warning"] if rows else ["warning"]
    return pd.DataFrame(rows), pd.DataFrame(warnings, columns=warning_columns)


def _portfolio_risk(holdings: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if holdings.empty:
        return pd.DataFrame(columns=[
            "scope", "feature_date", "top_fraction", "max_stock_weight",
            "max_industry_weight", "weight_hhi", "selected_count",
        ])
    for keys, group in holdings.groupby(["scope", "feature_date", "top_fraction"]):
        industry_weights = group.groupby("industry", dropna=False)["weight"].sum()
        rows.append({
            "scope": keys[0], "feature_date": keys[1], "top_fraction": keys[2],
            "max_stock_weight": float(group["weight"].max()),
            "max_industry_weight": float(industry_weights.max()),
            "weight_hhi": float((group["weight"] ** 2).sum()),
            "selected_count": int(len(group)),
        })
    return pd.DataFrame(rows)


def _monotonic(portfolios: pd.DataFrame, scope: str) -> bool:
    rows = portfolios[portfolios["scope"] == scope].set_index("top_fraction")
    if not {.1, .2, .3}.issubset(rows.index):
        return False
    values = rows["universe_net_excess_return"]
    return bool(values.loc[.1] >= values.loc[.2] >= values.loc[.3])
