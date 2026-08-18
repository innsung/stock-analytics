from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from src.ml.diagnostics_v2 import _rank_features, _split
from src.ml.diagnostics_v3 import (
    Candidate, _apply_universe_history, _bank_safe, _fit_predict,
    _read_universe_history, _registered_lockbox_start,
    _research_cutoff_and_lockbox_novelty,
)
from src.ml.diagnostics_v31 import (
    _apply_total_return_labels, _bootstrap_mean_ci, _concentration,
    _ic_rows, _monotonic, _portfolio_risk, _read_security_master,
    _read_total_return_history, _total_return_audit,
)
from src.ml.models import load_ml_dataset


CORPORATE_ACTION_COLUMNS = {
    "code", "effective_date", "action_type", "adjustment_factor",
    "cash_amount", "known_at", "source",
}


@dataclass(frozen=True)
class V32Candidate:
    strategy_name: str
    model_name: str
    target_kind: str = "excess_regression"
    financial_threshold: float = 0.0
    momentum_weight: float = 0.0
    risk_weight: float = 0.0
    timing_threshold: float = 0.0
    loss_guard: bool = False

    @property
    def is_champion(self) -> bool:
        return self.strategy_name == "v31_champion"


def _candidates() -> list[V32Candidate]:
    """A small, predeclared Champion-Challenger set; no candidate proliferation."""
    return [
        V32Candidate("v31_champion", "elastic_net"),
        V32Candidate("ridge_financial", "ridge"),
        V32Candidate("quality_momentum_balanced", "elastic_net", financial_threshold=.50,
                     momentum_weight=.55, risk_weight=.15, timing_threshold=.40),
        V32Candidate("quality_momentum_defensive", "ridge", financial_threshold=.55,
                     momentum_weight=.45, risk_weight=.30, timing_threshold=.45),
        V32Candidate("quality_momentum_loss_guard", "elastic_net", financial_threshold=.50,
                     momentum_weight=.50, risk_weight=.25, timing_threshold=.40,
                     loss_guard=True),
    ]


def _normalise_date(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.replace("-", "", regex=False).str.strip()


def _read_corporate_actions(path: str | None) -> tuple[pd.DataFrame, bool, str]:
    if not path:
        return pd.DataFrame(columns=[*sorted(CORPORATE_ACTION_COLUMNS), "row_valid"]), \
            False, "CORPORATE_ACTION_INPUT_NOT_AVAILABLE"
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = CORPORATE_ACTION_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("기업행사 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    frame["effective_date"] = _normalise_date(frame["effective_date"])
    frame["known_at"] = _normalise_date(frame["known_at"])
    frame["adjustment_factor"] = pd.to_numeric(frame["adjustment_factor"], errors="coerce")
    frame["cash_amount"] = pd.to_numeric(frame["cash_amount"], errors="coerce").fillna(0.0)
    allowed = {"SPLIT", "REVERSE_SPLIT", "RIGHTS", "BONUS", "MERGER", "SPINOFF",
               "CASH_DIVIDEND", "ETF_DISTRIBUTION"}
    invalid = (
        frame["effective_date"].str.len().ne(8)
        | frame["known_at"].str.len().ne(8)
        | frame["known_at"].gt(frame["effective_date"])
        | ~frame["action_type"].isin(allowed)
        | frame["adjustment_factor"].isna()
        | frame["adjustment_factor"].le(0)
        | frame["source"].str.strip().eq("")
        | frame.duplicated(["code", "effective_date", "action_type"], keep=False)
    )
    verified = bool(not frame.empty and not invalid.any())
    frame["row_valid"] = ~invalid
    return frame, verified, ("VERIFIED_CORPORATE_ACTION_INPUT" if verified
                             else "INVALID_CORPORATE_ACTION_INPUT")


def _financial_point_in_time_audit(conn: sqlite3.Connection, data: pd.DataFrame,
                                   benchmark_code: str) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_sql_query(
        """SELECT code,feature_date,financial_disclosed_at,valuation_snapshot_date
           FROM ml_features WHERE benchmark_code=? ORDER BY feature_date,code""",
        conn, params=(benchmark_code,))
    if raw.empty:
        return pd.DataFrame(), {"status": "FINANCIAL_PIT_NOT_AVAILABLE",
                                "rows": 0, "verified": False}
    raw["code"] = raw["code"].astype(str).str.zfill(6)
    raw["feature_date"] = _normalise_date(raw["feature_date"])
    raw["financial_disclosed_at"] = _normalise_date(raw["financial_disclosed_at"])
    raw["valuation_snapshot_date"] = _normalise_date(raw["valuation_snapshot_date"])
    keys = data[["code", "feature_date"]].drop_duplicates()
    audit = keys.merge(raw, on=["code", "feature_date"], how="left")
    audit["financial_date_valid"] = (
        audit["financial_disclosed_at"].str.len().eq(8)
        & audit["financial_disclosed_at"].le(audit["feature_date"]))
    audit["valuation_date_valid"] = (
        audit["valuation_snapshot_date"].eq("")
        | (audit["valuation_snapshot_date"].str.len().eq(8)
           & audit["valuation_snapshot_date"].le(audit["feature_date"])))
    financial_columns = ["revenue_growth", "operating_margin", "roe", "debt_ratio",
                         "operating_cash_flow_positive", "reported_eps", "estimated_bps"]
    facts = data[["code", "feature_date", *financial_columns]].copy()
    facts["financial_fact_present"] = facts[financial_columns].notna().any(axis=1)
    audit = audit.merge(facts[["code", "feature_date", "financial_fact_present"]],
                        on=["code", "feature_date"], how="left")
    audit["row_valid"] = (~audit["financial_fact_present"].fillna(False)
                          | audit["financial_date_valid"]) & audit["valuation_date_valid"]
    verified = bool(not audit.empty and audit["row_valid"].all()
                    and audit["financial_fact_present"].any())
    return audit, {
        "status": "FINANCIAL_PIT_VERIFIED" if verified else "FINANCIAL_PIT_INCOMPLETE",
        "rows": int(len(audit)), "valid_rows": int(audit["row_valid"].sum()),
        "financial_fact_rows": int(audit["financial_fact_present"].sum()),
        "verified": verified,
    }


def _percentile(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates).rank(method="average", pct=True).fillna(.5)


def _strategy_scores(candidate: V32Candidate, train: pd.DataFrame,
                     test: pd.DataFrame) -> pd.DataFrame:
    financial = Candidate(candidate.model_name, candidate.target_kind, "financial_safe")
    raw_financial, _ = _fit_predict(financial, train, test)
    out = test.copy()
    out["financial_score"] = _percentile(
        pd.Series(raw_financial, index=out.index), out["feature_date"])
    momentum = out[["relative_20", "relative_60", "ma_60_gap"]].mean(axis=1)
    risk = 1 - out[["volatility_20", "volatility_60", "atr_14_pct"]].mean(axis=1)
    out["momentum_score"] = _percentile(momentum, out["feature_date"])
    out["risk_score"] = _percentile(risk, out["feature_date"])
    if candidate.is_champion or candidate.strategy_name == "ridge_financial":
        out["score"] = out["financial_score"]
        out["signal_eligible"] = True
    else:
        financial_weight = 1 - candidate.momentum_weight - candidate.risk_weight
        out["score"] = (out["financial_score"] * financial_weight
                        + out["momentum_score"] * candidate.momentum_weight
                        + out["risk_score"] * candidate.risk_weight)
        out["signal_eligible"] = (
            out["financial_score"].ge(candidate.financial_threshold)
            & out["momentum_score"].ge(candidate.timing_threshold))
    return out


def _allocate(selected: pd.DataFrame, stock_cap: float, industry_cap: float,
              exposure: float) -> dict[str, float]:
    weights: dict[str, float] = {}
    industry_weights: dict[str, float] = {}
    remaining = exposure
    for row in selected.itertuples(index=False):
        industry = str(row.industry)
        room = max(0.0, industry_cap - industry_weights.get(industry, 0.0))
        weight = min(stock_cap, room, remaining)
        if weight <= 1e-12:
            continue
        weights[str(row.code)] = weight
        industry_weights[industry] = industry_weights.get(industry, 0.0) + weight
        remaining -= weight
        if remaining <= 1e-12:
            break
    return weights


def _portfolio_v32(predictions: pd.DataFrame, candidate: V32Candidate, horizon: int,
                   commission: float, tax: float, slippage: float, scope: str,
                   stock_cap: float = .15, industry_cap: float = .40
                   ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summaries: list[dict] = []
    holdings: list[dict] = []
    periods: list[dict] = []
    transitions: list[dict] = []
    dates = sorted(predictions["feature_date"].unique())[::horizon]
    for fraction in (.10, .20, .30):
        weights: dict[str, float] = {}
        previous: set[str] = set()
        loss_streak: dict[str, int] = {}
        model_equity = universe_equity = etf_equity = 1.0
        wins_universe = wins_etf = total_turnover = total_cost = 0.0
        evaluated = 0
        for day in dates:
            cross = predictions[predictions["feature_date"] == day].sort_values(
                ["score", "code"], ascending=[False, True]).copy()
            if cross.empty:
                continue
            eligible = cross[cross["signal_eligible"]].copy()
            guarded: set[str] = set()
            if candidate.loss_guard:
                guarded = {str(code) for code in eligible["code"]
                           if loss_streak.get(str(code), 0) >= 2}
                eligible = eligible[~eligible["code"].astype(str).map(
                    lambda code: loss_streak.get(code, 0) >= 2)]
            base_count = max(1, math.ceil(len(cross) * fraction))
            score_gap = float(eligible["score"].max() - eligible["score"].min()) \
                if len(eligible) > 1 else 0.0
            desired = (min(len(eligible), base_count) if candidate.is_champion else
                       min(len(eligible), max(base_count, 8 if score_gap < .10 else 5)))
            selected = eligible.head(desired)
            regime = int(pd.to_numeric(cross["market_regime"], errors="coerce").fillna(0).median())
            exposure = 1.0 if candidate.is_champion or candidate.strategy_name == "ridge_financial" \
                else (1.0 if regime > 0 else .65 if regime == 0 else .35)
            target = ({str(code): 1 / max(len(selected), 1) for code in selected["code"]}
                      if candidate.is_champion else
                      _allocate(selected, stock_cap, industry_cap, exposure))
            current = set(target)
            codes = set(weights) | current
            buys = sum(max(target.get(c, 0) - weights.get(c, 0), 0) for c in codes)
            sells = sum(max(weights.get(c, 0) - target.get(c, 0), 0) for c in codes)
            cost = buys * (commission + slippage) + sells * (commission + slippage + tax)
            selected_by_code = selected.set_index(selected["code"].astype(str), drop=False)
            gross = sum(target[c] * float(selected_by_code.loc[c, "forward_return"])
                        for c in current)
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
            evaluated += 1
            periods.append({
                "scope": scope, "feature_date": day, "top_fraction": fraction,
                "eligible_count": len(eligible), "selected_count": len(current),
                "target_exposure": sum(target.values()), "cash_weight": 1 - sum(target.values()),
                "market_regime": regime, "score_gap": score_gap,
                "gross_return": gross, "net_return": net,
                "universe_equal_weight_return": universe_return, "etf_return": etf_return,
                "universe_excess_return": net - universe_return,
                "etf_excess_return": net - etf_return,
                "turnover": buys + sells, "cost_pct": cost,
            })
            for code, weight in target.items():
                row = selected_by_code.loc[code]
                contribution = weight * float(row["forward_return"])
                holdings.append({
                    "scope": scope, "feature_date": day, "top_fraction": fraction,
                    "code": code, "name": row.get("name", ""), "industry": row["industry"],
                    "position_status": "HELD" if code in previous else "NEW",
                    "weight": weight, "score": row["score"],
                    "financial_score": row["financial_score"],
                    "momentum_score": row["momentum_score"], "risk_score": row["risk_score"],
                    "entry_close": row.get("close", np.nan),
                    "forward_return": row["forward_return"],
                    "weighted_gross_contribution": contribution,
                    "allocated_cost_pct": cost * weight / max(sum(target.values()), 1e-12),
                    "weighted_net_contribution": contribution - cost * weight
                    / max(sum(target.values()), 1e-12),
                })
                loss_streak[code] = loss_streak.get(code, 0) + 1 \
                    if float(row["forward_return"]) < 0 else 0
            # Two consecutive losses trigger one full rebalance-period cooldown.
            for code in guarded:
                loss_streak[code] = 0
            for code in sorted(previous - current):
                transitions.append({"scope": scope, "feature_date": day,
                                    "top_fraction": fraction, "code": code,
                                    "transition": "REMOVED", "reason": "RISK_OR_SIGNAL_FILTER"})
            for code in sorted(current - previous):
                transitions.append({"scope": scope, "feature_date": day,
                                    "top_fraction": fraction, "code": code,
                                    "transition": "ADDED", "reason": "ELIGIBLE_AND_RANKED"})
            previous, weights = current, target
        summaries.append({
            "scope": scope, "top_fraction": fraction, "periods": evaluated,
            "net_return": (model_equity - 1) * 100,
            "universe_equal_weight_return": (universe_equity - 1) * 100,
            "etf_return": (etf_equity - 1) * 100,
            "universe_net_excess_return": (model_equity - universe_equity) * 100,
            "etf_net_excess_return": (model_equity - etf_equity) * 100,
            "positive_vs_universe_rate": wins_universe / evaluated if evaluated else 0,
            "positive_vs_etf_rate": wins_etf / evaluated if evaluated else 0,
            "turnover": total_turnover, "total_cost_pct": total_cost,
        })
    return (pd.DataFrame(summaries), pd.DataFrame(holdings),
            pd.DataFrame(periods), pd.DataFrame(transitions))


def _evaluate(candidate: V32Candidate, train: pd.DataFrame, test: pd.DataFrame,
              horizon: int, commission: float, tax: float, slippage: float,
              split: str, stock_cap: float = .15, industry_cap: float = .40
              ) -> tuple[dict, pd.DataFrame, tuple[pd.DataFrame, ...]]:
    prediction = _strategy_scores(candidate, train, test)
    ic = _ic_rows(prediction, horizon)
    independent = ic[ic["non_overlapping"]]["rank_ic"]
    ci_low, ci_high = _bootstrap_mean_ci(independent)
    portfolio = _portfolio_v32(
        prediction, candidate, horizon, commission, tax, slippage, split,
        stock_cap, industry_cap)
    top20 = portfolio[0][portfolio[0]["top_fraction"].eq(.20)].iloc[0]
    metric = {
        "split": split, "strategy_name": candidate.strategy_name,
        "model_name": candidate.model_name, "is_champion": candidate.is_champion,
        "samples": len(test),
        "nonoverlap_rank_ic": float(independent.mean()) if independent.notna().any() else None,
        "nonoverlap_ic_ci_low": ci_low, "nonoverlap_ic_ci_high": ci_high,
        "independent_ic_periods": int(independent.notna().sum()),
        "top20_universe_net_excess_return": float(top20["universe_net_excess_return"]),
        "top20_etf_net_excess_return": float(top20["etf_net_excess_return"]),
        "top20_positive_vs_universe_rate": float(top20["positive_vs_universe_rate"]),
        "top20_positive_vs_etf_rate": float(top20["positive_vs_etf_rate"]),
    }
    return metric, prediction, portfolio


def _nested_select(data: pd.DataFrame, dates: np.ndarray, validation_start: str,
                   candidates: list[V32Candidate], min_train_days: int, fold_days: int,
                   embargo_days: int, horizon: int, commission: float, tax: float,
                   slippage: float, stock_cap: float, industry_cap: float
                   ) -> tuple[V32Candidate, pd.DataFrame, pd.DataFrame]:
    development_dates = dates[dates < validation_start]
    rows: list[dict] = []
    audits: list[dict] = []
    fold = 0
    for offset in range(min_train_days, len(development_dates), fold_days):
        test_dates = development_dates[offset:min(offset + fold_days, len(development_dates))]
        if len(test_dates) < max(10, fold_days // 3):
            continue
        train_cutoff_index = offset - embargo_days
        if train_cutoff_index <= 0:
            continue
        train_cutoff = development_dates[train_cutoff_index]
        test_start = test_dates[0]
        train = data[(data["feature_date"] < train_cutoff)
                     & (data["label_available_at"] < train_cutoff)]
        test = data[data["feature_date"].isin(test_dates)]
        if train.empty or test.empty:
            continue
        fold += 1
        audits.append({
            "fold": fold, "train_start": train["feature_date"].min(),
            "train_end": train["feature_date"].max(), "train_label_end": train["label_available_at"].max(),
            "embargo_start": train_cutoff, "test_start": test_start,
            "test_end": test_dates[-1], "purge_passed": bool(train["label_available_at"].max() < train_cutoff),
            "embargo_days": embargo_days,
        })
        for candidate in candidates:
            metric, _, _ = _evaluate(candidate, train, test, horizon, commission,
                                     tax, slippage, f"nested_fold_{fold}",
                                     stock_cap, industry_cap)
            metric["fold"] = fold
            rows.append(metric)
    metrics = pd.DataFrame(rows)
    audit = pd.DataFrame(audits)
    if metrics.empty:
        return candidates[0], metrics, audit
    aggregate = metrics.groupby("strategy_name").agg(
        folds=("fold", "nunique"),
        mean_ic=("nonoverlap_rank_ic", "mean"),
        mean_universe_excess=("top20_universe_net_excess_return", "mean"),
        mean_etf_excess=("top20_etf_net_excess_return", "mean"),
        dual_win_rate=("top20_universe_net_excess_return", lambda s: 0.0),
    ).reset_index()
    dual = metrics.assign(dual=(metrics["top20_universe_net_excess_return"] > 0)
                          & (metrics["top20_etf_net_excess_return"] > 0))
    rates = dual.groupby("strategy_name")["dual"].mean()
    aggregate["dual_win_rate"] = aggregate["strategy_name"].map(rates)
    for column, weight in (("mean_ic", .30), ("mean_universe_excess", .25),
                           ("mean_etf_excess", .25), ("dual_win_rate", .20)):
        aggregate[column + "_rank"] = aggregate[column].rank(pct=True)
    aggregate["selection_score"] = (
        aggregate["mean_ic_rank"] * .30 + aggregate["mean_universe_excess_rank"] * .25
        + aggregate["mean_etf_excess_rank"] * .25 + aggregate["dual_win_rate_rank"] * .20)
    winner = aggregate.sort_values(
        ["selection_score", "dual_win_rate", "mean_ic"], ascending=False).iloc[0]
    selected = next(c for c in candidates if c.strategy_name == winner["strategy_name"])
    metrics = metrics.merge(aggregate, on="strategy_name", how="left", suffixes=("", "_aggregate"))
    return selected, metrics, audit


def run_ml_diagnostics_v32(
        conn: sqlite3.Connection, horizon: int = 20, benchmark_code: str = "069500",
        validation_days: int = 126, test_days: int = 126, min_train_days: int = 504,
        fold_days: int = 126, embargo_days: int | None = None,
        commission: float = .015, tax: float = .18, slippage: float = .05,
        stock_cap: float = .15, industry_cap: float = .40,
        output_prefix: str = "ml_v32_h20", lockbox_start: str | None = None,
        universe_history_csv: str | None = None, total_return_csv: str | None = None,
        security_master_csv: str | None = None, corporate_actions_csv: str | None = None,
        rank_scope: str = "market") -> dict:
    embargo_days = horizon if embargo_days is None else embargo_days
    if embargo_days < horizon:
        raise ValueError("V3.2 embargo-days는 horizon 이상이어야 합니다.")
    if not 0 < stock_cap <= .15:
        raise ValueError("V3.2 stock-cap은 0보다 크고 0.15 이하여야 합니다.")
    if not 0 < industry_cap <= .40:
        raise ValueError("V3.2 industry-cap은 0보다 크고 0.40 이하여야 합니다.")
    data = load_ml_dataset(conn, horizon, benchmark_code)
    if data.empty:
        raise ValueError("V3.2 진단 데이터가 없습니다. build-feature-store를 먼저 실행하세요.")
    data["code"] = data["code"].astype(str).str.zfill(6)
    universe, universe_input_valid, universe_status = _read_universe_history(universe_history_csv)
    data, universe_audit, universe_coverage = _apply_universe_history(data, universe)
    universe_verified = bool(universe_input_valid and universe_coverage and not data.empty)
    if data.empty:
        raise ValueError("시점별 유니버스 적용 후 학습 가능한 행이 없습니다.")
    total_return, total_input_valid, total_input_status = _read_total_return_history(total_return_csv)
    data, total_labels, total_coverage = _apply_total_return_labels(
        data, total_return, total_input_valid, benchmark_code)
    names = _read_security_master(security_master_csv)
    data = data.merge(names, on="code", how="left")
    data["name"] = data["name"].fillna("")
    financial_audit, financial_summary = _financial_point_in_time_audit(
        conn, data, benchmark_code)
    corporate_actions, corporate_verified, corporate_status = _read_corporate_actions(
        corporate_actions_csv)
    data = _bank_safe(_rank_features(data, rank_scope))

    research_cutoff, fresh_lockbox = _research_cutoff_and_lockbox_novelty(
        conn, benchmark_code, horizon, str(data["feature_date"].max()), lockbox_start)
    existing = conn.execute(
        """SELECT 1 FROM ml_lockbox_registry WHERE benchmark_code=? AND horizon=?
           AND diagnostic_version=3""", (benchmark_code, horizon)).fetchone()
    if lockbox_start and not fresh_lockbox and not existing:
        registered_lockbox, lockbox_registered = None, False
    else:
        registered_lockbox, lockbox_registered = _registered_lockbox_start(
            conn, benchmark_code, horizon, lockbox_start)
    dates, validation_start, test_start, train, validation, published = _split(
        data, validation_days, test_days, registered_lockbox)

    candidates = _candidates()
    candidate_manifest = pd.DataFrame([asdict(candidate) | {
        "role": "CHAMPION" if candidate.is_champion else "CHALLENGER"
    } for candidate in candidates])
    selected, nested_metrics, nested_audit = _nested_select(
        data, dates, validation_start, candidates, min_train_days, fold_days,
        embargo_days, horizon, commission, tax, slippage, stock_cap, industry_cap)
    champion = candidates[0]
    validation_outputs = {}
    comparison_rows: list[dict] = []
    portfolio_frames: list[pd.DataFrame] = []
    holding_frames: list[pd.DataFrame] = []
    period_frames: list[pd.DataFrame] = []
    transition_frames: list[pd.DataFrame] = []
    for candidate in dict.fromkeys([champion, selected]):
        metric, prediction, portfolio = _evaluate(
            candidate, train, validation, horizon, commission, tax, slippage,
            f"validation_{candidate.strategy_name}", stock_cap, industry_cap)
        comparison_rows.append(metric)
        validation_outputs[candidate.strategy_name] = (prediction, portfolio)
        for frames, frame in zip((portfolio_frames, holding_frames, period_frames,
                                  transition_frames), portfolio):
            if not frame.empty:
                frames.append(frame)
    development = data[(data["feature_date"] < test_start)
                       & (data["label_available_at"] < test_start)]
    published_outputs = {}
    for candidate in dict.fromkeys([champion, selected]):
        metric, prediction, portfolio = _evaluate(
            candidate, development, published, horizon, commission, tax, slippage,
            f"published_{candidate.strategy_name}", stock_cap, industry_cap)
        comparison_rows.append(metric)
        published_outputs[candidate.strategy_name] = (prediction, portfolio)
        for frames, frame in zip((portfolio_frames, holding_frames, period_frames,
                                  transition_frames), portfolio):
            if not frame.empty:
                frames.append(frame)

    comparisons = pd.DataFrame(comparison_rows)
    portfolios = pd.concat(portfolio_frames, ignore_index=True)
    holdings = pd.concat(holding_frames, ignore_index=True) if holding_frames else pd.DataFrame()
    periods = pd.concat(period_frames, ignore_index=True)
    transitions = (pd.concat(transition_frames, ignore_index=True) if transition_frames else
                   pd.DataFrame(columns=["scope", "feature_date", "top_fraction", "code",
                                         "transition", "reason"]))
    concentration, warnings = _concentration(holdings)
    risks = _portfolio_risk(holdings)
    total_audit, total_summary = _total_return_audit(
        data, total_return, total_input_valid, benchmark_code, horizon)
    if total_audit.empty and len(total_audit.columns) == 0:
        total_audit = pd.DataFrame(columns=[
            "code", "feature_date", "label_available_at", "tr_entry", "tr_exit",
            "benchmark_tr_entry", "benchmark_tr_exit", "total_return",
            "benchmark_total_return", "price_label_difference",
            "benchmark_label_difference", "source",
        ])
    total_summary["labels_use_total_return"] = total_labels
    total_summary["full_label_coverage_rate"] = total_coverage
    total_summary["total_return_verified"] = bool(
        total_summary["total_return_verified"] and total_labels)

    validation_prediction, _ = validation_outputs[selected.strategy_name]
    published_prediction, _ = published_outputs[selected.strategy_name]
    validation_ic = _ic_rows(validation_prediction, horizon)
    published_ic = _ic_rows(published_prediction, horizon)
    selected_validation = comparisons[comparisons["split"].eq(
        f"validation_{selected.strategy_name}")].iloc[0]
    selected_nested = nested_metrics[nested_metrics["strategy_name"].eq(selected.strategy_name)]
    nested_dual_rate = float(((selected_nested["top20_universe_net_excess_return"] > 0)
                              & (selected_nested["top20_etf_net_excess_return"] > 0)).mean()) \
        if not selected_nested.empty else 0.0
    selected_holdings = holdings[(holdings["scope"].eq(f"validation_{selected.strategy_name}"))
                                 & holdings["top_fraction"].eq(.20)]
    held_rate = float(selected_holdings.groupby("code").size().max()
                      / selected_holdings["feature_date"].nunique()) \
        if not selected_holdings.empty else 1.0
    selected_risk = risks[(risks["scope"].eq(f"validation_{selected.strategy_name}"))
                          & risks["top_fraction"].eq(.20)]
    max_stock = float(selected_risk["max_stock_weight"].max()) if not selected_risk.empty else 1.0
    max_industry = float(selected_risk["max_industry_weight"].max()) if not selected_risk.empty else 1.0
    selected_portfolios = portfolios[portfolios["scope"].eq(
        f"validation_{selected.strategy_name}")]
    selected_top20 = selected_portfolios[selected_portfolios["top_fraction"].eq(.20)].iloc[0]
    selected_published_top20 = portfolios[
        portfolios["scope"].eq(f"published_{selected.strategy_name}")
        & portfolios["top_fraction"].eq(.20)].iloc[0]
    nested_clean = bool(not nested_audit.empty and nested_audit["purge_passed"].all()
                        and nested_audit["embargo_days"].ge(horizon).all()
                        and nested_audit["test_end"].max() < validation_start)
    criteria = {
        "nested_purged_selection_completed": int(nested_audit["fold"].nunique()) >= 2
        if not nested_audit.empty else False,
        "nested_selection_leakage_free": nested_clean,
        "validation_untouched_during_selection": nested_clean,
        "v31_champion_preserved": any(c.is_champion for c in candidates),
        "point_in_time_universe_verified": universe_verified,
        "total_return_history_verified": bool(total_summary["total_return_verified"]),
        "financial_disclosure_point_in_time_verified": bool(financial_summary["verified"]),
        "corporate_action_input_verified": corporate_verified,
        "majority_nested_folds_dual_benchmark_positive": nested_dual_rate > .5,
        "validation_nonoverlap_rank_ic_positive": bool(
            pd.notna(selected_validation["nonoverlap_rank_ic"])
            and selected_validation["nonoverlap_rank_ic"] > 0),
        "validation_nonoverlap_ic_ci_low_positive": bool(
            pd.notna(selected_validation["nonoverlap_ic_ci_low"])
            and selected_validation["nonoverlap_ic_ci_low"] > 0),
        "minimum_12_independent_validation_periods": int(
            selected_validation["independent_ic_periods"]) >= 12,
        "validation_dual_benchmark_top20_positive": bool(
            selected_top20["universe_net_excess_return"] > 0
            and selected_top20["etf_net_excess_return"] > 0),
        "validation_top_fraction_monotonic": _monotonic(
            selected_portfolios.assign(scope="validation"), "validation"),
        "validation_top20_not_fixed_single_portfolio": held_rate < .80,
        "validation_stock_weight_at_or_below_15pct": max_stock <= stock_cap + 1e-9,
        "validation_industry_weight_at_or_below_40pct": max_industry <= industry_cap + 1e-9,
        "immutable_v3_lockbox_registered": lockbox_registered,
        "fresh_v3_lockbox_after_research_cutoff": fresh_lockbox,
        "fresh_lockbox_dual_benchmark_top20_positive": bool(
            fresh_lockbox and selected_published_top20["universe_net_excess_return"] > 0
            and selected_published_top20["etf_net_excess_return"] > 0),
    }
    verdict = "ADOPT" if all(criteria.values()) else "RESEARCH_ONLY"
    fallback = {
        "selection_failure": "KEEP_V31_CHAMPION",
        "all_models_fail": "EQUAL_WEIGHT_OR_BENCHMARK_ETF_SHADOW_COMPARISON_ONLY",
        "live_order_permission": "BLOCKED",
    }
    summary = {
        "version": "3.2", "verdict": verdict,
        "champion_strategy": champion.strategy_name,
        "selected_strategy": selected.strategy_name,
        "selected_challenger": None if selected.is_champion else selected.strategy_name,
        "selected_model": selected.model_name,
        "candidate_count": len(candidates), "nested_fold_count": int(len(nested_audit)),
        "embargo_days": embargo_days, "rank_scope": rank_scope, "horizon": horizon,
        "validation_period": [validation["feature_date"].min(), validation["feature_date"].max()],
        "published_test_period": [published["feature_date"].min(), published["feature_date"].max()],
        "research_seen_through": research_cutoff,
        "universe_history_status": universe_status,
        "total_return_input_status": total_input_status,
        "corporate_action_status": corporate_status,
        "financial_point_in_time_audit": financial_summary,
        "total_return_audit": total_summary,
        "nested_dual_benchmark_positive_rate": nested_dual_rate,
        "max_validation_top20_held_rate": held_rate,
        "max_validation_stock_weight": max_stock,
        "max_validation_industry_weight": max_industry,
        "criteria": criteria, "fallback_policy": fallback,
        "cost_assumptions_pct": {"commission_one_way": commission, "sell_tax": tax,
                                 "slippage_one_way": slippage},
        "risk_limits": {"stock_cap": stock_cap, "industry_cap": industry_cap},
        "safety": "RESEARCH_AND_SHADOW_ONLY_NO_LIVE_ORDERS",
        "note": "V3.1 remains the frozen Champion. V3.2 selection uses only nested pre-validation folds; the 2026 published test remains previously seen.",
    }
    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)

    def save(frame: pd.DataFrame, suffix: str) -> None:
        frame.to_csv(prefix.with_name(prefix.name + suffix), index=False, encoding="utf-8-sig")

    save(nested_metrics, "_nested_model_selection.csv")
    save(candidate_manifest, "_candidate_manifest.csv")
    save(nested_audit, "_purge_embargo_audit.csv")
    save(comparisons, "_champion_challenger.csv")
    save(portfolios, "_dual_benchmark_portfolios.csv")
    save(periods, "_portfolio_periods.csv")
    save(holdings, "_holding_contributions.csv")
    save(transitions, "_portfolio_transitions.csv")
    save(concentration, "_concentration.csv")
    save(risks, "_portfolio_risk.csv")
    save(warnings, "_risk_warnings.csv")
    save(validation_ic, "_validation_ic.csv")
    save(published_ic, "_published_test_ic.csv")
    save(universe_audit, "_universe_audit.csv")
    save(total_audit, "_total_return_audit.csv")
    save(financial_audit, "_financial_pit_audit.csv")
    save(corporate_actions, "_corporate_action_audit.csv")
    prediction_columns = ["code", "name", "feature_date", "industry", "close",
                          "forward_return", "benchmark_forward_return", "excess_return",
                          "financial_score", "momentum_score", "risk_score",
                          "signal_eligible", "score"]
    save(published_prediction[prediction_columns], "_published_test_predictions.csv")
    prefix.with_name(prefix.name + "_fallback_policy.json").write_text(
        json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")
    prefix.with_name(prefix.name + "_verdict.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
