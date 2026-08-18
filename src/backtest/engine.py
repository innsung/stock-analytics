from dataclasses import dataclass, field
import math

import pandas as pd


@dataclass(frozen=True)
class StrategyParams:
    fast_window: int = 20
    slow_window: int = 120
    rsi_min: float = 45
    rsi_max: float = 68
    stop_loss: float = -0.07
    take_profit: float = 0.20
    min_holding_days: int = 5
    require_trend_confirmation: bool = True
    core_ratio: float = 0.35
    atr_multiple: float = 3.0


@dataclass
class BacktestResult:
    total_return: float
    benchmark_return: float
    excess_return: float
    cagr: float
    benchmark_cagr: float
    mdd: float
    benchmark_mdd: float
    sharpe: float
    benchmark_sharpe: float
    win_rate: float
    profit_factor: float
    avg_holding_days: float
    trades: int
    total_cost: float
    start_date: str
    end_date: str
    trade_log: pd.DataFrame = field(repr=False)
    equity_curve: pd.DataFrame = field(repr=False)
    yearly_performance: pd.DataFrame = field(repr=False)
    regime_performance: pd.DataFrame = field(repr=False)


def _cagr(start_value: float, end_value: float, years: float) -> float:
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return 0.0
    return ((end_value / start_value) ** (1 / years) - 1) * 100


def run_ma_rsi_strategy(
    data: pd.DataFrame,
    stop_loss: float = -0.07,
    take_profit: float = 0.20,
    initial_capital: float = 10_000_000,
    commission_pct: float = 0.015,
    sell_tax_pct: float = 0.18,
    slippage_pct: float = 0.05,
    fast_window: int = 20,
    slow_window: int = 120,
    rsi_min: float = 45,
    rsi_max: float = 68,
    min_holding_days: int = 5,
    require_trend_confirmation: bool = True,
    evaluation_start: str | pd.Timestamp | None = None,
    evaluation_end: str | pd.Timestamp | None = None,
    core_ratio: float = 0.35,
    atr_multiple: float = 3.0,
) -> BacktestResult:
    """전일 종가 신호를 다음 거래일 시가에 체결하는 현금 100% 전략.

    비용 인수는 퍼센트 단위다. 예: 0.015는 0.015%를 뜻한다.
    """
    required = {"date", "open", "close"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError("백테스트 필수 열 누락: " + ", ".join(sorted(missing)))
    if initial_capital <= 0:
        raise ValueError("initial_capital은 0보다 커야 합니다.")
    if not 0 <= core_ratio < 1:
        raise ValueError("core_ratio는 0 이상 1 미만이어야 합니다.")

    if fast_window >= slow_window:
        raise ValueError("fast_window는 slow_window보다 작아야 합니다.")
    frame = data.dropna(subset=list(required)).sort_values("date").copy()
    frame["date"] = pd.to_datetime(frame["date"], format="mixed")
    frame["ma_fast"] = frame["close"].rolling(fast_window).mean()
    frame["ma_slow"] = frame["close"].rolling(slow_window).mean()
    frame["slow_slope"] = frame["ma_slow"].diff(5)
    previous_close = frame["close"].shift(1)
    if {"high", "low"}.issubset(frame.columns):
        true_range = pd.concat([(frame["high"] - frame["low"]).abs(),
                                (frame["high"] - previous_close).abs(),
                                (frame["low"] - previous_close).abs()], axis=1).max(axis=1)
    else:
        true_range = (frame["close"] - previous_close).abs()
    frame["atr14"] = true_range.rolling(14).mean()
    if "rsi14" not in frame:
        delta = frame["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        frame["rsi14"] = 100 - 100 / (1 + gain / loss.replace(0, float("nan")))
        frame.loc[(loss == 0) & (gain > 0), "rsi14"] = 100
        frame.loc[(gain == 0) & (loss > 0), "rsi14"] = 0
        frame.loc[(gain == 0) & (loss == 0), "rsi14"] = 50
    frame = frame.dropna(subset=["ma_fast", "ma_slow", "rsi14"])
    frame = frame[(frame["open"] > 0) & (frame["close"] > 0)].reset_index(drop=True)
    evaluation_start = pd.Timestamp(evaluation_start) if evaluation_start is not None else frame.iloc[0]["date"]
    evaluation_end = pd.Timestamp(evaluation_end) if evaluation_end is not None else frame.iloc[-1]["date"]
    eligible = frame.index[frame["date"] >= evaluation_start]
    if len(eligible):
        frame = frame.iloc[max(int(eligible[0]) - 1, 0):]
    frame = frame[frame["date"] <= evaluation_end].reset_index(drop=True)
    evaluation_frame = frame[frame["date"] >= evaluation_start]
    if len(frame) < 2:
        raise ValueError("백테스트에는 지표 계산 후 최소 2거래일이 필요합니다.")

    commission = commission_pct / 100
    sell_tax = sell_tax_pct / 100
    slippage = slippage_pct / 100
    cash = float(initial_capital) * (1 - core_ratio)
    core_cash = float(initial_capital) * core_ratio
    core_quantity = 0
    core_initialized = False
    quantity = 0
    entry_price = 0.0
    entry_cost = 0.0
    entry_date = None
    entry_index = None
    peak_close = 0.0
    total_cost = 0.0
    trades: list[dict] = []
    equity_records: list[tuple[pd.Timestamp, float]] = []

    for i, row in frame.iterrows():
        if row["date"] < evaluation_start:
            continue
        if not core_initialized:
            core_price = float(row["open"]) * (1 + slippage)
            core_quantity = math.floor(core_cash / (core_price * (1 + commission)))
            if core_quantity > 0:
                gross = core_quantity * core_price
                fee = gross * commission
                core_cash -= gross + fee
                total_cost += fee + core_quantity * float(row["open"]) * slippage
            core_initialized = True
        if i > 0:
            previous = frame.iloc[i - 1]
            if quantity == 0:
                trend_ok = (not require_trend_confirmation) or previous["slow_slope"] > 0
                buy_signal = (
                    previous["ma_fast"] > previous["ma_slow"]
                    and previous["close"] >= previous["ma_fast"]
                    and rsi_min <= previous["rsi14"] <= rsi_max
                    and trend_ok
                )
                if buy_signal:
                    execution_price = float(row["open"]) * (1 + slippage)
                    quantity = math.floor(cash / (execution_price * (1 + commission)))
                    if quantity > 0:
                        gross = quantity * execution_price
                        fee = gross * commission
                        cash -= gross + fee
                        total_cost += fee + quantity * float(row["open"]) * slippage
                        entry_price, entry_cost, entry_date, entry_index = execution_price, gross + fee, row["date"], i
                        peak_close = float(row["close"])
            else:
                prior_return = float(previous["close"]) / entry_price - 1
                peak_close = max(peak_close, float(previous["close"]))
                held = i - entry_index
                atr_ratio = float(previous["atr14"]) / float(previous["close"]) if pd.notna(previous["atr14"]) else abs(stop_loss) / 2
                volatility_stop = -max(abs(stop_loss), min(.15, atr_ratio * 2))
                stop_signal = prior_return <= volatility_stop
                strong_trend = (previous["ma_fast"] > previous["ma_slow"] and
                                previous["slow_slope"] > 0 and previous["close"] >= previous["ma_fast"])
                trailing_width = max(.07, min(.20, atr_ratio * atr_multiple))
                trailing_signal = held >= min_holding_days and previous["close"] <= peak_close * (1 - trailing_width)
                take_signal = held >= min_holding_days and not strong_trend and prior_return >= take_profit
                trend_signal = held >= min_holding_days and (
                    previous["ma_fast"] < previous["ma_slow"] or previous["close"] < previous["ma_slow"]
                )
                exit_signal = stop_signal or trailing_signal or take_signal or trend_signal
                if exit_signal:
                    execution_price = float(row["open"]) * (1 - slippage)
                    gross = quantity * execution_price
                    fee = gross * commission
                    tax = gross * sell_tax
                    proceeds = gross - fee - tax
                    cash += proceeds
                    total_cost += fee + tax + quantity * float(row["open"]) * slippage
                    pnl = proceeds - entry_cost
                    trades.append({
                        "entry_date": entry_date.strftime("%Y-%m-%d"),
                        "exit_date": row["date"].strftime("%Y-%m-%d"),
                        "entry_price": round(entry_price, 2), "exit_price": round(execution_price, 2),
                        "quantity": quantity, "pnl": round(pnl, 2),
                        "return_pct": round(pnl / entry_cost * 100, 4),
                        "holding_days": (row["date"] - entry_date).days,
                        "exit_reason": ("volatility_stop" if stop_signal else
                                        "trailing_stop" if trailing_signal else
                                        "take_profit" if take_signal else "trend_exit"),
                    })
                    quantity, entry_price, entry_cost, entry_date, entry_index = 0, 0.0, 0.0, None, None
        equity_records.append((row["date"], cash + quantity * float(row["close"]) +
                               core_cash + core_quantity * float(row["close"])))

    # 마지막 날 보유분은 종가에 청산해 모든 성과를 확정손익으로 비교한다.
    if quantity > 0:
        last = frame.iloc[-1]
        execution_price = float(last["close"]) * (1 - slippage)
        gross = quantity * execution_price
        fee, tax = gross * commission, gross * sell_tax
        proceeds = gross - fee - tax
        cash += proceeds
        total_cost += fee + tax + quantity * float(last["close"]) * slippage
        pnl = proceeds - entry_cost
        trades.append({
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "exit_date": last["date"].strftime("%Y-%m-%d"),
            "entry_price": round(entry_price, 2), "exit_price": round(execution_price, 2),
            "quantity": quantity, "pnl": round(pnl, 2), "return_pct": round(pnl / entry_cost * 100, 4),
            "holding_days": (last["date"] - entry_date).days,
            "exit_reason": "end_of_period",
        })
    last = frame.iloc[-1]
    if core_quantity > 0:
        core_exit = float(last["close"]) * (1 - slippage)
        core_gross = core_quantity * core_exit
        core_fee, core_tax = core_gross * commission, core_gross * sell_tax
        core_cash += core_gross - core_fee - core_tax
        total_cost += core_fee + core_tax + core_quantity * float(last["close"]) * slippage
    final_cash = cash + core_cash
    equity_records[-1] = (last["date"], final_cash)

    equity = pd.Series([value for _, value in equity_records], index=[day for day, _ in equity_records])
    daily_returns = equity.pct_change().fillna(0)
    mdd = (equity / equity.cummax() - 1).min() * 100
    std = daily_returns.std(ddof=0)
    sharpe = (daily_returns.mean() / std * math.sqrt(252)) if std > 0 else 0.0
    years = max((evaluation_frame.iloc[-1]["date"] - evaluation_frame.iloc[0]["date"]).days / 365.25, 1 / 365.25)

    # 동일한 시작일 시가에 매수하고 마지막 날 종가에 매도하는 벤치마크.
    benchmark_buy = float(evaluation_frame.iloc[0]["open"]) * (1 + slippage)
    benchmark_qty = math.floor(initial_capital / (benchmark_buy * (1 + commission)))
    benchmark_buy_cost = benchmark_qty * benchmark_buy * (1 + commission)
    benchmark_cash = initial_capital - benchmark_buy_cost
    benchmark_sell = float(evaluation_frame.iloc[-1]["close"]) * (1 - slippage)
    benchmark_gross = benchmark_qty * benchmark_sell
    benchmark_final = benchmark_cash + benchmark_gross * (1 - commission - sell_tax)

    benchmark_values = benchmark_cash + benchmark_qty * evaluation_frame["close"].astype(float)
    benchmark_values.index = pd.to_datetime(evaluation_frame["date"])
    benchmark_values.iloc[-1] = benchmark_final
    benchmark_daily = benchmark_values.pct_change().fillna(0)
    benchmark_mdd = (benchmark_values / benchmark_values.cummax() - 1).min() * 100
    benchmark_std = benchmark_daily.std(ddof=0)
    benchmark_sharpe = (benchmark_daily.mean() / benchmark_std * math.sqrt(252)) if benchmark_std > 0 else 0.0

    equity_curve = pd.DataFrame({"strategy_equity": equity, "benchmark_equity": benchmark_values}).dropna()
    curve_returns = equity_curve.pct_change().fillna(0)
    yearly_rows = []
    for year, group in curve_returns.groupby(curve_returns.index.year):
        yearly_rows.append({
            "year": int(year),
            "strategy_return": round((group["strategy_equity"].add(1).prod() - 1) * 100, 2),
            "benchmark_return": round((group["benchmark_equity"].add(1).prod() - 1) * 100, 2),
        })
    yearly_performance = pd.DataFrame(yearly_rows)

    regime_source = evaluation_frame.set_index("date").reindex(equity_curve.index)
    momentum_60 = regime_source["close"].pct_change(60)
    regimes = pd.Series("횡보", index=equity_curve.index)
    regimes[(regime_source["close"] > regime_source["ma_slow"]) & (momentum_60 > .05)] = "상승"
    regimes[(regime_source["close"] < regime_source["ma_slow"]) & (momentum_60 < -.05)] = "하락"
    regime_rows = []
    for regime in ("상승", "하락", "횡보"):
        mask = regimes == regime
        selected_returns = curve_returns.loc[mask]
        regime_rows.append({
            "regime": regime, "days": int(mask.sum()),
            "strategy_return": round((selected_returns["strategy_equity"].add(1).prod() - 1) * 100, 2),
            "benchmark_return": round((selected_returns["benchmark_equity"].add(1).prod() - 1) * 100, 2),
        })
    regime_performance = pd.DataFrame(regime_rows)

    trade_log = pd.DataFrame(trades)
    wins = trade_log[trade_log["pnl"] > 0]["pnl"].sum() if not trade_log.empty else 0.0
    losses = -trade_log[trade_log["pnl"] < 0]["pnl"].sum() if not trade_log.empty else 0.0
    strategy_return = (final_cash / initial_capital - 1) * 100
    benchmark_return = (benchmark_final / initial_capital - 1) * 100
    return BacktestResult(
        total_return=round(strategy_return, 2), benchmark_return=round(benchmark_return, 2),
        excess_return=round(strategy_return - benchmark_return, 2),
        cagr=round(_cagr(initial_capital, final_cash, years), 2),
        benchmark_cagr=round(_cagr(initial_capital, benchmark_final, years), 2),
        mdd=round(float(mdd), 2), benchmark_mdd=round(float(benchmark_mdd), 2),
        sharpe=round(float(sharpe), 2), benchmark_sharpe=round(float(benchmark_sharpe), 2),
        win_rate=round((trade_log["pnl"].gt(0).mean() * 100) if not trade_log.empty else 0, 2),
        profit_factor=round(float(wins / losses), 2) if losses > 0 else (float("inf") if wins > 0 else 0.0),
        avg_holding_days=round(float(trade_log["holding_days"].mean()), 2) if not trade_log.empty else 0.0,
        trades=len(trade_log), total_cost=round(total_cost, 2),
        start_date=evaluation_frame.iloc[0]["date"].strftime("%Y-%m-%d"),
        end_date=evaluation_frame.iloc[-1]["date"].strftime("%Y-%m-%d"), trade_log=trade_log,
        equity_curve=equity_curve, yearly_performance=yearly_performance,
        regime_performance=regime_performance,
    )
