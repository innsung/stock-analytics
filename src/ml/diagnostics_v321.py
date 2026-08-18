from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from src.ml.diagnostics_features_v321 import _rank_features, _split
from src.ml.diagnostics_research_v321 import (
    Candidate, _apply_universe_history, _bank_safe, _fit_predict,
    _read_universe_history, _registered_lockbox_start,
    _research_cutoff_and_lockbox_novelty,
)
from src.ml.diagnostics_portfolio_v321 import (
    _apply_total_return_labels, _bootstrap_mean_ci, _concentration,
    _ic_rows, _monotonic, _portfolio_risk, _read_security_master,
    _read_total_return_history, _total_return_audit,
)
from src.ml.models import load_ml_dataset
from src.ml.data_integrity_v321 import selection_persistence_audit


RESEARCH_SEEN_THROUGH = "20260709"

CORPORATE_ACTION_COLUMNS = {
    "code", "effective_date", "action_type", "adjustment_factor",
    "cash_amount", "known_at", "source",
}


@dataclass(frozen=True)
class V321Candidate:
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
        return self.strategy_name == "current_champion"


def _candidates() -> list[V321Candidate]:
    """A small, predeclared Champion-Challenger set; no candidate proliferation."""
    return [
        V321Candidate("current_champion", "elastic_net"),
        V321Candidate("ridge_financial", "ridge"),
        V321Candidate("quality_momentum_balanced", "elastic_net", financial_threshold=.50,
                     momentum_weight=.55, risk_weight=.15, timing_threshold=.40),
        V321Candidate("quality_momentum_defensive", "ridge", financial_threshold=.55,
                     momentum_weight=.45, risk_weight=.30, timing_threshold=.45),
        V321Candidate("quality_momentum_loss_guard", "elastic_net", financial_threshold=.50,
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
        """SELECT code,feature_date,financial_disclosed_at,valuation_snapshot_date,valuation_known_at,
                  valuation_per,valuation_pbr,historical_per,historical_pbr
           FROM ml_features WHERE benchmark_code=? ORDER BY feature_date,code""",
        conn, params=(benchmark_code,))
    if raw.empty:
        return pd.DataFrame(), {"status": "FINANCIAL_DISCLOSURE_PIT_PARTIAL",
                                "rows": 0, "verified": False,
                                "reason": "ML_FEATURES_NOT_AVAILABLE"}
    raw["code"] = raw["code"].astype(str).str.zfill(6)
    for col in ("feature_date", "financial_disclosed_at", "valuation_snapshot_date", "valuation_known_at"):
        raw[col] = _normalise_date(raw[col])
    keys = data[["code", "feature_date"]].drop_duplicates()
    audit = keys.merge(raw, on=["code", "feature_date"], how="left")
    financial_columns = ["revenue_growth", "operating_margin", "roe", "debt_ratio",
                         "operating_cash_flow_positive", "reported_eps", "estimated_bps"]
    facts = data[["code", "feature_date", *financial_columns]].copy()
    facts["financial_fact_present"] = facts[financial_columns].notna().any(axis=1)
    audit = audit.merge(facts[["code", "feature_date", "financial_fact_present"]],
                        on=["code", "feature_date"], how="left")
    audit["valuation_fact_present"] = audit[["valuation_per", "valuation_pbr"]].notna().any(axis=1)
    audit["financial_date_valid"] = (
        audit["financial_disclosed_at"].str.len().eq(8)
        & audit["financial_disclosed_at"].le(audit["feature_date"]))
    # V3.2.1: valuation facts never receive FULL PIT credit without an actual observation date.
    audit["valuation_date_valid"] = (
        audit["valuation_snapshot_date"].str.len().eq(8)
        & audit["valuation_snapshot_date"].le(audit["feature_date"]))
    audit["valuation_known_at_valid"] = (
        audit["valuation_known_at"].str.len().eq(8)
        & audit["valuation_known_at"].le(audit["valuation_snapshot_date"])
        & audit["valuation_known_at"].le(audit["feature_date"]))
    valuations = pd.read_sql_query(
        """SELECT v.code,v.snapshot_date,COALESCE(m.known_at,v.snapshot_date) AS known_at,
                  v.per,v.pbr,v.market_cap,v.source
           FROM valuation_snapshots v LEFT JOIN valuation_snapshot_meta m
             ON m.code=v.code AND m.snapshot_date=v.snapshot_date
           ORDER BY v.code,v.snapshot_date""", conn)
    if not valuations.empty:
        valuations["code"] = valuations["code"].astype(str).str.zfill(6)
        valuations["snapshot_date"] = _normalise_date(valuations["snapshot_date"])
        valuations = valuations.rename(columns={
            "snapshot_date": "valuation_snapshot_date", "known_at": "observed_known_at", "per": "observed_per",
            "pbr": "observed_pbr", "market_cap": "observed_market_cap",
            "source": "valuation_source"})
        audit = audit.merge(valuations,
                            on=["code", "valuation_snapshot_date"], how="left")
    else:
        audit["observed_known_at"] = ""
        audit["observed_per"] = np.nan
        audit["observed_pbr"] = np.nan
        audit["observed_market_cap"] = np.nan
        audit["valuation_source"] = ""
    audit["valuation_source_row_found"] = audit["valuation_source"].fillna("").astype(str).ne("")
    audit["financial_rule"] = np.where(
        audit["financial_fact_present"].fillna(False),
        "FINANCIAL_FACT_REQUIRES_DISCLOSED_AT", "NO_STORED_FINANCIAL_FACT")
    audit["valuation_rule"] = np.where(
        audit["valuation_fact_present"].fillna(False),
        "VALUATION_FACT_REQUIRES_SNAPSHOT_DATE_KNOWN_AT_AND_SOURCE_ROW", "NO_STORED_VALUATION_FACT")
    audit["row_valid"] = (
        (~audit["financial_fact_present"].fillna(False) | audit["financial_date_valid"])
        & (~audit["valuation_fact_present"].fillna(False)
           | (audit["valuation_date_valid"] & audit["valuation_known_at_valid"] & audit["valuation_source_row_found"])))
    has_financial = bool(audit["financial_fact_present"].fillna(False).any())
    has_valuation = bool(audit["valuation_fact_present"].fillna(False).any())
    full = bool(not audit.empty and audit["row_valid"].all()
                and has_financial and has_valuation
                and audit.loc[audit["valuation_fact_present"], "valuation_date_valid"].all()
                and audit.loc[audit["valuation_fact_present"], "valuation_known_at_valid"].all())
    status = "FULL_PIT_VERIFIED" if full else "FINANCIAL_DISCLOSURE_PIT_PARTIAL"
    return audit, {
        "status": status, "rows": int(len(audit)),
        "valid_rows": int(audit["row_valid"].sum()),
        "financial_fact_rows": int(audit["financial_fact_present"].fillna(False).sum()),
        "valuation_fact_rows": int(audit["valuation_fact_present"].fillna(False).sum()),
        "valuation_source_rows": int(audit["valuation_source_row_found"].sum()),
        "features_use_financial_information": True,
        "verified": full,
        "full_pit_requires_valuation_snapshot_date": True,
        "full_pit_requires_valuation_known_at": True,
    }

def _percentile(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates).rank(method="average", pct=True).fillna(.5)


def _strategy_scores(candidate: V321Candidate, train: pd.DataFrame,
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
    else:
        financial_weight = 1 - candidate.momentum_weight - candidate.risk_weight
        out["score"] = (out["financial_score"] * financial_weight
                        + out["momentum_score"] * candidate.momentum_weight
                        + out["risk_score"] * candidate.risk_weight)
    # Common entry gate applies to Champion and every Challenger.
    financial_floor = max(.35, candidate.financial_threshold)
    momentum_floor = max(.35, candidate.timing_threshold)
    out["financial_eligible"] = out["financial_score"].ge(financial_floor)
    out["momentum_eligible"] = out["momentum_score"].ge(momentum_floor)
    out["signal_eligible"] = out["financial_eligible"] & out["momentum_eligible"]
    return out

def _allocate(selected: pd.DataFrame, stock_cap: float, industry_cap: float,
              exposure: float, loss_streak: dict[str, int]) -> tuple[dict[str, float], dict[str, str]]:
    """Hard-cap allocator. Unallocatable capital stays cash; no cap may be relaxed."""
    weights: dict[str, float] = {}
    reasons: dict[str, str] = {}
    industry_weights: dict[str, float] = {}
    remaining = max(0.0, min(1.0, exposure))
    for row in selected.itertuples(index=False):
        code = str(row.code)
        streak = int(loss_streak.get(code, 0))
        if streak >= 3:
            reasons[code] = "THREE_LOSSES_ONE_REBALANCE_EXCLUSION"
            continue
        industry = str(row.industry)
        room = max(0.0, industry_cap - industry_weights.get(industry, 0.0))
        per_stock_limit = stock_cap * (.5 if streak == 2 else 1.0)
        if streak == 2:
            reasons[code] = "TWO_LOSSES_HALF_NEW_WEIGHT"
        weight = min(per_stock_limit, room, remaining)
        if weight <= 1e-12:
            reasons.setdefault(code, "CAPACITY_OR_EXPOSURE_LIMIT")
            continue
        weights[code] = weight
        industry_weights[industry] = industry_weights.get(industry, 0.0) + weight
        remaining -= weight
        if remaining <= 1e-12:
            break
    return weights, reasons


def _market_exposure(regime: int) -> float:
    return 1.0 if regime > 0 else .70 if regime == 0 else .40


def _portfolio_v32(predictions: pd.DataFrame, candidate: V321Candidate, horizon: int,
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
        cooldown_once: set[str] = set()
        model_equity = universe_equity = etf_equity = 1.0
        wins_universe = wins_etf = simultaneous_wins = total_turnover = total_cost = 0.0
        evaluated = 0
        for day in dates:
            cross = predictions[predictions["feature_date"] == day].sort_values(
                ["score", "code"], ascending=[False, True]).copy()
            if cross.empty:
                continue
            eligible = cross[cross["signal_eligible"]].copy()
            base_count = max(7, math.ceil(len(cross) * fraction))
            desired = min(len(eligible), base_count)
            selected = eligible.head(desired).copy()
            selected["score_rank"] = np.arange(1, len(selected) + 1)
            selected["score_percentile"] = selected["score"].rank(method="average", pct=True)
            regime = int(pd.to_numeric(cross["market_regime"], errors="coerce").fillna(0).median())
            exposure = _market_exposure(regime)
            # If fewer than 7 pass the gate, keep the missing capacity as cash.
            target, guard_reasons = _allocate(selected, stock_cap, industry_cap, exposure, loss_streak)
            current = set(target)
            codes = set(weights) | current
            buys = sum(max(target.get(c, 0) - weights.get(c, 0), 0) for c in codes)
            sells = sum(max(weights.get(c, 0) - target.get(c, 0), 0) for c in codes)
            cost = buys * (commission + slippage) + sells * (commission + slippage + tax)
            selected_by_code = selected.set_index(selected["code"].astype(str), drop=False)
            gross = sum(target[c] * float(selected_by_code.loc[c, "forward_return"]) for c in current)
            universe_return = float(cross["forward_return"].mean())
            etf_return = float(cross["benchmark_forward_return"].mean())
            net = gross - cost
            model_equity *= 1 + net / 100
            universe_equity *= 1 + universe_return / 100
            etf_equity *= 1 + etf_return / 100
            beat_u, beat_e = net > universe_return, net > etf_return
            wins_universe += int(beat_u)
            wins_etf += int(beat_e)
            simultaneous_wins += int(beat_u and beat_e)
            total_turnover += buys + sells
            total_cost += cost
            evaluated += 1
            periods.append({
                "scope": scope, "feature_date": day, "top_fraction": fraction,
                "eligible_count": len(eligible), "selected_count": len(current),
                "minimum_stock_target": 7, "insufficient_eligible_for_minimum": len(eligible) < 7,
                "target_exposure": sum(target.values()), "cash_weight": 1 - sum(target.values()),
                "market_regime": regime, "market_exposure_limit": exposure,
                "gross_return": gross, "net_return": net,
                "universe_equal_weight_return": universe_return, "etf_return": etf_return,
                "universe_excess_return": net - universe_return, "etf_excess_return": net - etf_return,
                "simultaneous_dual_win": bool(beat_u and beat_e),
                "turnover": buys + sells, "cost_pct": cost,
            })
            # Update loss streak only after observing the completed holding period.
            for code, weight in target.items():
                row = selected_by_code.loc[code]
                contribution = weight * float(row["forward_return"])
                holdings.append({
                    "scope": scope, "feature_date": day, "top_fraction": fraction,
                    "code": code, "name": row.get("name", ""), "industry": row["industry"],
                    "position_status": "HELD" if code in previous else "NEW",
                    "weight": weight, "score": row["score"],
                    "score_rank": int(row["score_rank"]),
                    "score_percentile": float(row["score_percentile"]),
                    "financial_score": row["financial_score"],
                    "momentum_score": row["momentum_score"], "risk_score": row["risk_score"],
                    "entry_close": row.get("close", np.nan),
                    "forward_return": row["forward_return"],
                    "weighted_gross_contribution": contribution,
                    "allocated_cost_pct": cost * weight / max(sum(target.values()), 1e-12),
                    "weighted_net_contribution": contribution - cost * weight / max(sum(target.values()), 1e-12),
                    "pre_entry_loss_streak": int(loss_streak.get(code, 0)),
                    "risk_guard_reason": guard_reasons.get(code, ""),
                })
                loss_streak[code] = loss_streak.get(code, 0) + 1 if float(row["forward_return"]) < 0 else 0
                if loss_streak[code] >= 3:
                    cooldown_once.add(code)
            for code in list(cooldown_once):
                if code not in current and loss_streak.get(code, 0) >= 3:
                    # exclusion lasts exactly one rebalance period, then reset to allow re-entry
                    loss_streak[code] = 0
                    cooldown_once.discard(code)
            for code in sorted(previous - current):
                transitions.append({"scope": scope, "feature_date": day,
                                    "top_fraction": fraction, "code": code,
                                    "transition": "REMOVED", "reason": guard_reasons.get(code, "RISK_OR_SIGNAL_FILTER")})
            for code in sorted(current - previous):
                transitions.append({"scope": scope, "feature_date": day,
                                    "top_fraction": fraction, "code": code,
                                    "transition": "ADDED", "reason": guard_reasons.get(code, "ELIGIBLE_AND_RANKED")})
            previous, weights = current, target
        summaries.append({
            "scope": scope, "top_fraction": fraction, "periods": evaluated,
            "net_return": (model_equity - 1) * 100,
            "universe_equal_weight_return": (universe_equity - 1) * 100,
            "etf_return": (etf_equity - 1) * 100,
            "universe_net_excess_return": (model_equity - universe_equity) * 100,
            "etf_net_excess_return": (model_equity - etf_equity) * 100,
            "cumulative_dual_outperformance": bool(model_equity > universe_equity and model_equity > etf_equity),
            "positive_vs_universe_rate": wins_universe / evaluated if evaluated else 0,
            "positive_vs_etf_rate": wins_etf / evaluated if evaluated else 0,
            "simultaneous_dual_win_rate": simultaneous_wins / evaluated if evaluated else 0,
            "turnover": total_turnover, "total_cost_pct": total_cost,
        })
    return (pd.DataFrame(summaries), pd.DataFrame(holdings), pd.DataFrame(periods), pd.DataFrame(transitions))


def _fixation_metrics(holdings: pd.DataFrame, periods: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if holdings.empty:
        return pd.DataFrame(columns=["scope", "top_fraction", "mean_jaccard", "max_stock_held_rate", "mean_turnover"])
    for (scope, fraction), group in holdings.groupby(["scope", "top_fraction"]):
        by_date = {d: set(g["code"].astype(str)) for d, g in group.groupby("feature_date")}
        dates = sorted(by_date)
        jac = []
        for a, b in zip(dates, dates[1:]):
            union = by_date[a] | by_date[b]
            jac.append(len(by_date[a] & by_date[b]) / len(union) if union else 1.0)
        held_rate = group.groupby("code")["feature_date"].nunique().max() / max(len(dates), 1)
        pg = periods[(periods["scope"] == scope) & (periods["top_fraction"] == fraction)]
        rows.append({"scope": scope, "top_fraction": fraction,
                     "mean_jaccard": float(np.mean(jac)) if jac else 1.0,
                     "max_stock_held_rate": float(held_rate),
                     "mean_turnover": float(pg["turnover"].mean()) if not pg.empty else 0.0,
                     "portfolio_fixed_flag": bool(jac and np.mean(jac) >= .80),
                     "single_stock_fixed_flag": bool(held_rate >= .80)})
    return pd.DataFrame(rows)


def _constraint_audit(holdings: pd.DataFrame, periods: pd.DataFrame, stock_cap: float, industry_cap: float) -> pd.DataFrame:
    rows = []
    keys = periods[["scope", "feature_date", "top_fraction"]].drop_duplicates()
    for rec in keys.itertuples(index=False):
        g = holdings[(holdings["scope"] == rec.scope) & (holdings["feature_date"] == rec.feature_date)
                     & (holdings["top_fraction"] == rec.top_fraction)]
        max_stock = float(g["weight"].max()) if not g.empty else 0.0
        max_ind = float(g.groupby("industry")["weight"].sum().max()) if not g.empty else 0.0
        p = periods[(periods["scope"] == rec.scope) & (periods["feature_date"] == rec.feature_date)
                    & (periods["top_fraction"] == rec.top_fraction)].iloc[0]
        rows.append({"scope": rec.scope, "feature_date": rec.feature_date, "top_fraction": rec.top_fraction,
                     "max_stock_weight": max_stock, "max_industry_weight": max_ind,
                     "target_exposure": float(p["target_exposure"]),
                     "market_exposure_limit": float(p["market_exposure_limit"]),
                     "stock_cap_violation": max_stock > stock_cap + 1e-9,
                     "industry_cap_violation": max_ind > industry_cap + 1e-9,
                     "exposure_violation": float(p["target_exposure"]) > float(p["market_exposure_limit"]) + 1e-9})
    return pd.DataFrame(rows)


def _outlier_stress(holdings: pd.DataFrame, periods: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (scope, fraction), g in holdings.groupby(["scope", "top_fraction"]):
        contrib = g.groupby("code")["weighted_net_contribution"].sum().sort_values(ascending=False)
        if contrib.empty:
            continue
        removed = str(contrib.index[0])
        pg = periods[(periods["scope"] == scope) & (periods["top_fraction"] == fraction)].sort_values("feature_date").copy()
        removed_by_day = g[g["code"].astype(str) == removed].groupby("feature_date")["weighted_net_contribution"].sum()
        pg["stressed_net"] = pg["net_return"] - pg["feature_date"].map(removed_by_day).fillna(0.0)
        meq = ueq = eeq = 1.0
        dualwins = 0
        for r in pg.itertuples(index=False):
            meq *= 1 + float(r.stressed_net) / 100
            ueq *= 1 + float(r.universe_equal_weight_return) / 100
            eeq *= 1 + float(r.etf_return) / 100
            dualwins += int(r.stressed_net > r.universe_equal_weight_return and r.stressed_net > r.etf_return)
        rows.append({"scope": scope, "top_fraction": fraction, "removed_top_contributor_code": removed,
                     "removed_contribution_pct": float(contrib.iloc[0]),
                     "stressed_net_return": (meq - 1) * 100,
                     "stressed_universe_excess_return": (meq - ueq) * 100,
                     "stressed_etf_excess_return": (meq - eeq) * 100,
                     "stressed_simultaneous_dual_win_rate": dualwins / len(pg) if len(pg) else 0.0,
                     "stressed_dual_positive": bool(meq > ueq and meq > eeq)})
    return pd.DataFrame(rows)

def _evaluate(candidate: V321Candidate, train: pd.DataFrame, test: pd.DataFrame,
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
                   candidates: list[V321Candidate], min_train_days: int, fold_days: int,
                   embargo_days: int, horizon: int, commission: float, tax: float,
                   slippage: float, stock_cap: float, industry_cap: float
                   ) -> tuple[V321Candidate, pd.DataFrame, pd.DataFrame]:
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


def run_ml_diagnostics_v321(
        conn: sqlite3.Connection, horizon: int = 20, benchmark_code: str = "069500",
        validation_days: int = 126, test_days: int = 126, min_train_days: int = 504,
        fold_days: int = 126, embargo_days: int | None = None,
        commission: float = .015, tax: float = .18, slippage: float = .05,
        stock_cap: float = .15, industry_cap: float = .40,
        output_prefix: str = "ml_v321_h20", lockbox_start: str | None = None,
        universe_history_csv: str | None = None, total_return_csv: str | None = None,
        security_master_csv: str | None = None, corporate_actions_csv: str | None = None,
        rank_scope: str = "market") -> dict:
    embargo_days = horizon if embargo_days is None else embargo_days
    if embargo_days < horizon:
        raise ValueError("V3.2.1 embargo-days는 horizon 이상이어야 합니다.")
    if not 0 < stock_cap <= .15:
        raise ValueError("V3.2.1 stock-cap은 0보다 크고 0.15 이하여야 합니다.")
    if not 0 < industry_cap <= .40:
        raise ValueError("V3.2.1 industry-cap은 0보다 크고 0.40 이하여야 합니다.")
    data = load_ml_dataset(conn, horizon, benchmark_code)
    # Sealed-test maintenance: no research tuning is allowed to consume observations after 2026-07-09.
    data = data[data["feature_date"].astype(str) <= RESEARCH_SEEN_THROUGH].copy()
    if data.empty:
        raise ValueError("V3.2.1 진단 데이터가 없습니다. build-feature-store를 먼저 실행하세요.")
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

    _registry_cutoff, fresh_lockbox = _research_cutoff_and_lockbox_novelty(
        conn, benchmark_code, horizon, RESEARCH_SEEN_THROUGH, lockbox_start)
    research_cutoff = RESEARCH_SEEN_THROUGH
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
    fixation = _fixation_metrics(holdings, periods)
    persistence = selection_persistence_audit(holdings, periods)
    constraint_audit = _constraint_audit(holdings, periods, stock_cap, industry_cap)
    outlier_stress = _outlier_stress(holdings, periods)
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
    selected_fixation = fixation[(fixation["scope"].eq(f"validation_{selected.strategy_name}"))
                                 & fixation["top_fraction"].eq(.20)]
    mean_jaccard = float(selected_fixation["mean_jaccard"].iloc[0]) if not selected_fixation.empty else 1.0
    mean_turnover = float(selected_fixation["mean_turnover"].iloc[0]) if not selected_fixation.empty else 0.0
    selected_persistence = persistence[(persistence["scope"].eq(f"validation_{selected.strategy_name}"))
                                       & persistence["top_fraction"].eq(.20)]
    persistent_rows = selected_persistence[selected_persistence["persistent_flag"]] if not selected_persistence.empty else pd.DataFrame()
    unsupported_persistent = int((~persistent_rows["persistent_but_supported"]).sum()) if not persistent_rows.empty else 0
    selected_constraints = constraint_audit[constraint_audit["scope"].eq(f"validation_{selected.strategy_name}")]
    published_constraints = constraint_audit[constraint_audit["scope"].eq(f"published_{selected.strategy_name}")]
    all_validation_constraints_ok = bool(not selected_constraints.empty and not selected_constraints[["stock_cap_violation", "industry_cap_violation", "exposure_violation"]].any().any())
    all_published_constraints_ok = bool(not published_constraints.empty and not published_constraints[["stock_cap_violation", "industry_cap_violation", "exposure_violation"]].any().any())
    selected_stress = outlier_stress[(outlier_stress["scope"].eq(f"validation_{selected.strategy_name}"))
                                     & outlier_stress["top_fraction"].eq(.20)]
    stress_dual_positive = bool(not selected_stress.empty and selected_stress["stressed_dual_positive"].iloc[0])
    nested_clean = bool(not nested_audit.empty and nested_audit["purge_passed"].all()
                        and nested_audit["embargo_days"].ge(horizon).all()
                        and nested_audit["test_end"].max() < validation_start)
    criteria = {
        "nested_purged_selection_completed": int(nested_audit["fold"].nunique()) >= 3
        if not nested_audit.empty else False,
        "nested_selection_leakage_free": nested_clean,
        "validation_untouched_during_selection": nested_clean,
        "current_champion_preserved": any(c.is_champion for c in candidates),
        "common_risk_overlay_applied_to_all_strategies": True,
        "point_in_time_universe_verified": universe_verified,
        "total_return_history_verified": bool(total_summary["total_return_verified"]),
        "financial_disclosure_point_in_time_verified": bool(financial_summary["verified"]),
        "corporate_action_input_verified": corporate_verified,
        "nested_simultaneous_dual_win_rate_at_least_60pct": nested_dual_rate >= .60,
        "validation_nonoverlap_rank_ic_positive": bool(
            pd.notna(selected_validation["nonoverlap_rank_ic"]) and selected_validation["nonoverlap_rank_ic"] > 0),
        "validation_nonoverlap_ic_ci_low_positive": bool(
            pd.notna(selected_validation["nonoverlap_ic_ci_low"]) and selected_validation["nonoverlap_ic_ci_low"] > 0),
        "minimum_12_independent_validation_periods": int(selected_validation["independent_ic_periods"]) >= 12,
        "validation_cumulative_dual_benchmark_positive": bool(selected_top20["cumulative_dual_outperformance"]),
        "validation_simultaneous_dual_win_rate_at_least_60pct": bool(selected_top20["simultaneous_dual_win_rate"] >= .60),
        "validation_top_fraction_monotonic": _monotonic(
            selected_portfolios.assign(scope="validation"), "validation"),
        "validation_portfolio_not_fixed_jaccard": mean_jaccard < .80,
        "validation_individual_stock_not_fixed": held_rate < .80,
        "persistent_stock_selection_economically_supported": unsupported_persistent == 0,
        "validation_turnover_observed": mean_turnover > 0,
        "validation_hard_constraints_no_violations": all_validation_constraints_ok,
        "published_test_hard_constraints_no_violations": all_published_constraints_ok,
        "single_top_contributor_removed_still_dual_positive": stress_dual_positive,
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
        "version": "3.2.1", "verdict": verdict,
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
        "nested_simultaneous_dual_win_rate": nested_dual_rate,
        "validation_simultaneous_dual_win_rate": float(selected_top20["simultaneous_dual_win_rate"]),
        "validation_cumulative_dual_outperformance": bool(selected_top20["cumulative_dual_outperformance"]),
        "published_test_simultaneous_dual_win_rate": float(selected_published_top20["simultaneous_dual_win_rate"]),
        "published_test_cumulative_dual_outperformance": bool(selected_published_top20["cumulative_dual_outperformance"]),
        "max_validation_top20_held_rate": held_rate,
        "validation_mean_portfolio_jaccard": mean_jaccard,
        "validation_mean_turnover": mean_turnover,
        "validation_persistent_stock_count": int(len(persistent_rows)),
        "validation_unsupported_persistent_stock_count": unsupported_persistent,
        "max_validation_stock_weight": max_stock,
        "max_validation_industry_weight": max_industry,
        "criteria": criteria, "fallback_policy": fallback,
        "cost_assumptions_pct": {"commission_one_way": commission, "sell_tax": tax,
                                 "slippage_one_way": slippage},
        "risk_limits": {"minimum_stocks": 7, "stock_cap": stock_cap, "industry_cap": industry_cap,
                        "neutral_market_exposure": .70, "down_market_exposure": .40,
                        "two_loss_new_weight_multiplier": .50,
                        "three_loss_exclusion_rebalances": 1},
        "sealed_test_policy": {"research_seen_through": RESEARCH_SEEN_THROUGH,
                               "retuning_after_20260710": "PROHIBITED",
                               "daily_shadow": "CONTINUES",
                               "live_orders": "BLOCKED",
                               "next_normal_sealed_test_estimate": "AROUND_2027_02"},
        "safety": "RESEARCH_AND_SHADOW_ONLY_NO_LIVE_ORDERS",
        "note": "The V3.2.1 Champion is frozen. Research data is frozen through 2026-07-09 and the 2026 public test remains previously seen, not a fresh sealed test.",
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
    save(fixation, "_fixation_audit.csv")
    save(persistence, "_selection_persistence_audit.csv")
    save(constraint_audit, "_hard_constraint_audit.csv")
    save(outlier_stress, "_outlier_contribution_stress.csv")
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
