from dataclasses import dataclass, field
from datetime import timedelta
import math

import numpy as np
import pandas as pd


@dataclass
class PortfolioResult:
    total_return: float
    benchmark_return: float
    excess_return: float
    cagr: float
    benchmark_cagr: float
    mdd: float
    benchmark_mdd: float
    sharpe: float
    benchmark_sharpe: float
    total_cost: float
    trades: int
    start_date: str
    end_date: str
    equity_curve: pd.DataFrame = field(repr=False)
    trade_log: pd.DataFrame = field(repr=False)
    allocation_log: pd.DataFrame = field(repr=False)
    yearly_performance: pd.DataFrame = field(repr=False)


@dataclass
class LockboxResult:
    development: PortfolioResult
    lockbox: PortfolioResult
    verdict: str


def _metrics(curve: pd.Series) -> tuple[float, float]:
    returns = curve.pct_change().fillna(0)
    mdd = (curve / curve.cummax() - 1).min() * 100
    std = returns.std(ddof=0)
    sharpe = returns.mean() / std * math.sqrt(252) if std > 0 else 0.0
    return float(mdd), float(sharpe)


def _cagr(start: float, end: float, dates: pd.DatetimeIndex) -> float:
    years = max((dates[-1] - dates[0]).days / 365.25, 1 / 365.25)
    return ((end / start) ** (1 / years) - 1) * 100 if end > 0 else -100.0


def _indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    data["ma20"] = data["close"].rolling(20).mean()
    data["ma60"] = data["close"].rolling(60).mean()
    data["ma120"] = data["close"].rolling(120).mean()
    data["ma120_slope"] = data["ma120"].diff(20)
    previous = data["close"].shift(1)
    tr = pd.concat([(data["high"] - data["low"]).abs(),
                    (data["high"] - previous).abs(), (data["low"] - previous).abs()], axis=1).max(axis=1)
    data["atr14"] = tr.rolling(14).mean()
    data["vol60"] = data["close"].pct_change().rolling(60).std() * math.sqrt(252)
    delta = data["close"].diff()
    gain, loss = delta.clip(lower=0).rolling(14).mean(), (-delta.clip(upper=0)).rolling(14).mean()
    data["rsi14"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    data.loc[(loss == 0) & (gain > 0), "rsi14"] = 100
    data.loc[(gain == 0) & (loss == 0), "rsi14"] = 50
    return data


def _market_budget(row: pd.Series) -> tuple[str, float, float]:
    if row["close"] > row["ma120"] and row["ma60"] > row["ma120"] and row["ma120_slope"] > 0:
        return "강한상승", .95, .70
    if row["close"] > row["ma120"]:
        return "상승", .75, .50
    if row["close"] >= row["ma120"] * .90:
        return "횡보", .45, .25
    return "하락", .15, .05


def _capped_weights(raw: dict[str, float], industries: dict[str, str], stock_cap: float,
                    sector_cap: float, target_total: float) -> dict[str, float]:
    if not raw or sum(raw.values()) <= 0:
        return {code: 0.0 for code in raw}
    weights = {code: value / sum(raw.values()) * target_total for code, value in raw.items()}
    for _ in range(4):
        weights = {code: min(weight, stock_cap) for code, weight in weights.items()}
        sectors: dict[str, float] = {}
        for code, weight in weights.items():
            sectors[industries.get(code, "미분류")] = sectors.get(industries.get(code, "미분류"), 0) + weight
        for sector, total in sectors.items():
            if total > sector_cap:
                scale = sector_cap / total
                weights = {code: weight * scale if industries.get(code, "미분류") == sector else weight
                           for code, weight in weights.items()}
    return weights


def run_dynamic_portfolio(
    frames: dict[str, pd.DataFrame], benchmark_frame: pd.DataFrame,
    industries: dict[str, str], initial_capital: float = 100_000_000,
    rebalance: str = "monthly", stock_cap: float = .20, sector_cap: float = .35,
    commission_pct: float = .015, sell_tax_pct: float = .18, slippage_pct: float = .05,
    evaluation_start=None, evaluation_end=None,
) -> PortfolioResult:
    if len(frames) < 2:
        raise ValueError("포트폴리오에는 최소 2개 종목이 필요합니다.")
    prepared = {code: _indicators(frame.set_index(pd.to_datetime(frame["date"])).drop(columns="date"))
                for code, frame in frames.items()}
    benchmark = _indicators(benchmark_frame.set_index(pd.to_datetime(benchmark_frame["date"])).drop(columns="date"))
    common_dates = benchmark.index
    for frame in prepared.values():
        common_dates = common_dates.intersection(frame.index)
    common_dates = common_dates.sort_values()
    common_dates = common_dates[common_dates >= max(frame.dropna(subset=["ma120"]).index.min() for frame in [benchmark, *prepared.values()])]
    if evaluation_start is not None:
        common_dates = common_dates[common_dates >= pd.Timestamp(evaluation_start)]
    if evaluation_end is not None:
        common_dates = common_dates[common_dates <= pd.Timestamp(evaluation_end)]
    if len(common_dates) < 2:
        raise ValueError("평가 가능한 공통 거래일이 부족합니다.")

    commission, sell_tax, slippage = commission_pct / 100, sell_tax_pct / 100, slippage_pct / 100
    cash = float(initial_capital)
    holdings = {code: {"core": 0, "tactical": 0, "peak": 0.0} for code in frames}
    trades, allocations, equity_records = [], [], []
    total_cost = 0.0

    def sell(code, bucket, qty, price, day, reason):
        nonlocal cash, total_cost
        if qty <= 0: return
        execution = price * (1 - slippage); gross = qty * execution
        fee, tax = gross * commission, gross * sell_tax
        cash += gross - fee - tax; total_cost += fee + tax + qty * price * slippage
        holdings[code][bucket] -= qty
        trades.append({"date": day.strftime("%Y-%m-%d"), "code": code, "side": "SELL",
                       "bucket": bucket, "quantity": qty, "price": round(execution, 2), "reason": reason})

    def buy(code, bucket, qty, price, day, reason):
        nonlocal cash, total_cost
        if qty <= 0: return
        execution = price * (1 + slippage); unit = execution * (1 + commission)
        qty = min(qty, math.floor(cash / unit))
        if qty <= 0: return
        gross = qty * execution; fee = gross * commission
        cash -= gross + fee; total_cost += fee + qty * price * slippage
        holdings[code][bucket] += qty
        holdings[code]["peak"] = max(holdings[code]["peak"], price)
        trades.append({"date": day.strftime("%Y-%m-%d"), "code": code, "side": "BUY",
                       "bucket": bucket, "quantity": qty, "price": round(execution, 2), "reason": reason})

    previous_period = None
    for position, day in enumerate(common_dates):
        previous_day = common_dates[max(position - 1, 0)]
        stopped = set()
        if position > 0:
            for code, frame in prepared.items():
                state, previous_row = holdings[code], frame.loc[previous_day]
                if state["tactical"] > 0:
                    state["peak"] = max(state["peak"], float(previous_row["close"]))
                    atr_ratio = previous_row["atr14"] / previous_row["close"] if pd.notna(previous_row["atr14"]) else .03
                    trail_width = max(.07, min(.20, float(atr_ratio) * 3))
                    if previous_row["close"] <= state["peak"] * (1 - trail_width) or previous_row["close"] < previous_row["ma120"]:
                        sell(code, "tactical", state["tactical"], float(frame.loc[day, "open"]), day, "atr_trailing_stop")
                        stopped.add(code)

        period = (day.year, day.month) if rebalance == "monthly" else (day.year, (day.month - 1) // 3)
        if period != previous_period:
            market_row = benchmark.loc[previous_day]
            regime, exposure, core_budget = _market_budget(market_row)
            tactical_budget = exposure - core_budget
            inverse_vol = {}
            for code, frame in prepared.items():
                row = frame.loc[previous_day]
                if pd.notna(row["vol60"]) and pd.notna(row["atr14"]):
                    daily_risk = max(float(row["atr14"] / row["close"]),
                                     float(row["vol60"]) / math.sqrt(252), .005)
                    inverse_vol[code] = 1 / daily_risk
            eligible = {code: value for code, value in inverse_vol.items()
                        if code not in stopped and prepared[code].loc[previous_day, "ma20"] > prepared[code].loc[previous_day, "ma120"]
                        and prepared[code].loc[previous_day, "ma120_slope"] > 0
                        and 40 <= prepared[code].loc[previous_day, "rsi14"] <= 72}
            core_sum, tactical_sum = sum(inverse_vol.values()), sum(eligible.values())
            core_pre = {code: value / core_sum * core_budget for code, value in inverse_vol.items()} if core_sum else {}
            tactical_pre = {code: value / tactical_sum * tactical_budget for code, value in eligible.items()} if tactical_sum else {}
            combined_pre = {code: core_pre.get(code, 0) + tactical_pre.get(code, 0) for code in holdings}
            combined_weights = _capped_weights(combined_pre, industries, stock_cap, sector_cap,
                                               min(exposure, sum(combined_pre.values())))
            core_weights, tactical_weights = {}, {}
            for code, combined in combined_weights.items():
                before = combined_pre.get(code, 0)
                core_share = core_pre.get(code, 0) / before if before > 0 else 0
                core_weights[code] = combined * core_share
                tactical_weights[code] = combined * (1 - core_share)
            open_equity = cash + sum((state["core"] + state["tactical"]) * float(prepared[code].loc[day, "open"])
                                     for code, state in holdings.items())
            targets = {code: {"core": math.floor(open_equity * core_weights.get(code, 0) / float(prepared[code].loc[day, "open"])),
                              "tactical": math.floor(open_equity * tactical_weights.get(code, 0) / float(prepared[code].loc[day, "open"]))}
                       for code in holdings}
            for code, target in targets.items():
                price = float(prepared[code].loc[day, "open"])
                for bucket in ("core", "tactical"):
                    excess = holdings[code][bucket] - target[bucket]
                    if excess > 0: sell(code, bucket, excess, price, day, "rebalance")
            for code, target in targets.items():
                price = float(prepared[code].loc[day, "open"])
                for bucket in ("core", "tactical"):
                    shortage = target[bucket] - holdings[code][bucket]
                    if shortage > 0: buy(code, bucket, shortage, price, day, "rebalance")
            for code in holdings:
                allocations.append({"date": day.strftime("%Y-%m-%d"), "regime": regime,
                    "code": code, "industry": industries.get(code, "미분류"),
                    "target_exposure": exposure, "target_core_weight": round(core_weights.get(code, 0), 6),
                    "target_tactical_weight": round(tactical_weights.get(code, 0), 6),
                    "target_total_weight": round(combined_weights.get(code, 0), 6),
                    "core_quantity": holdings[code]["core"], "tactical_quantity": holdings[code]["tactical"],
                    "cash_after_rebalance": round(cash, 2)})
            previous_period = period
        equity = cash + sum((state["core"] + state["tactical"]) * float(prepared[code].loc[day, "close"])
                            for code, state in holdings.items())
        equity_records.append((day, equity))

    last_day = common_dates[-1]
    for code, state in holdings.items():
        for bucket in ("core", "tactical"):
            sell(code, bucket, state[bucket], float(prepared[code].loc[last_day, "close"]), last_day, "end_of_period")
    equity_records[-1] = (last_day, cash)
    equity = pd.Series(dict(equity_records)).sort_index()

    benchmark_open = float(benchmark.loc[common_dates[0], "open"])
    benchmark_buy = benchmark_open * (1 + slippage)
    benchmark_qty = math.floor(initial_capital / (benchmark_buy * (1 + commission)))
    benchmark_cash = initial_capital - benchmark_qty * benchmark_buy * (1 + commission)
    benchmark_curve = benchmark_cash + benchmark_qty * benchmark.loc[common_dates, "close"]
    final_mid = float(benchmark.loc[last_day, "close"]); final_execution = final_mid * (1 - slippage)
    benchmark_curve.iloc[-1] = benchmark_cash + benchmark_qty * final_execution * (1 - commission - sell_tax)

    mdd, sharpe = _metrics(equity); benchmark_mdd, benchmark_sharpe = _metrics(benchmark_curve)
    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    benchmark_return = (benchmark_curve.iloc[-1] / initial_capital - 1) * 100
    curve = pd.DataFrame({"strategy_equity": equity, "benchmark_equity": benchmark_curve})
    returns = curve.pct_change().fillna(0)
    yearly = []
    for year, group in returns.groupby(returns.index.year):
        yearly.append({"year": int(year), "strategy_return": round((1 + group["strategy_equity"]).prod() * 100 - 100, 2),
                       "benchmark_return": round((1 + group["benchmark_equity"]).prod() * 100 - 100, 2)})
    return PortfolioResult(
        round(total_return, 2), round(benchmark_return, 2), round(total_return - benchmark_return, 2),
        round(_cagr(initial_capital, equity.iloc[-1], equity.index), 2),
        round(_cagr(initial_capital, benchmark_curve.iloc[-1], benchmark_curve.index), 2),
        round(mdd, 2), round(benchmark_mdd, 2), round(sharpe, 2), round(benchmark_sharpe, 2),
        round(total_cost, 2), len(trades), common_dates[0].strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d"),
        curve, pd.DataFrame(trades), pd.DataFrame(allocations), pd.DataFrame(yearly),
    )


def run_lockbox(frames, benchmark_frame, industries, lockbox_months=12, **kwargs) -> LockboxResult:
    last_date = min(pd.to_datetime(frame["date"]).max() for frame in [benchmark_frame, *frames.values()])
    lock_start = pd.Timestamp(last_date) - pd.DateOffset(months=lockbox_months) + timedelta(days=1)
    development = run_dynamic_portfolio(frames, benchmark_frame, industries,
                                        evaluation_end=lock_start - timedelta(days=1), **kwargs)
    lockbox = run_dynamic_portfolio(frames, benchmark_frame, industries,
                                    evaluation_start=lock_start, **kwargs)
    verdict = "통과" if lockbox.excess_return > 0 and lockbox.sharpe >= lockbox.benchmark_sharpe and lockbox.mdd >= lockbox.benchmark_mdd else "보류"
    return LockboxResult(development, lockbox, verdict)
