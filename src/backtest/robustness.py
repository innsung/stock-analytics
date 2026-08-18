from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult, StrategyParams, run_ma_rsi_strategy


@dataclass
class SensitivityResult:
    positive_rate: float
    benchmark_beat_rate: float
    median_return: float
    return_dispersion: float
    verdict: str
    details: pd.DataFrame = field(repr=False)


@dataclass
class MonteCarloResult:
    simulations: int
    median_return: float
    return_p05: float
    return_p95: float
    loss_probability: float
    median_mdd: float
    mdd_p05: float
    verdict: str
    details: pd.DataFrame = field(repr=False)


def parameter_sensitivity(
    data: pd.DataFrame,
    base: StrategyParams = StrategyParams(),
    initial_capital: float = 10_000_000,
    commission_pct: float = .015,
    sell_tax_pct: float = .18,
    slippage_pct: float = .05,
) -> SensitivityResult:
    variants = {base}
    for fast in {max(5, base.fast_window - 5), base.fast_window, base.fast_window + 5}:
        variants.add(replace(base, fast_window=fast))
    for slow in {max(base.fast_window + 10, base.slow_window - 20), base.slow_window, base.slow_window + 20}:
        variants.add(replace(base, slow_window=slow))
    for rsi_max in {base.rsi_max - 3, base.rsi_max, base.rsi_max + 3}:
        variants.add(replace(base, rsi_max=rsi_max))
    for stop in {base.stop_loss - .02, base.stop_loss, base.stop_loss + .02}:
        variants.add(replace(base, stop_loss=stop))
    for take in {base.take_profit - .05, base.take_profit, base.take_profit + .05}:
        variants.add(replace(base, take_profit=take))

    rows = []
    for params in sorted(variants, key=str):
        result = run_ma_rsi_strategy(
            data, initial_capital=initial_capital, commission_pct=commission_pct,
            sell_tax_pct=sell_tax_pct, slippage_pct=slippage_pct,
            fast_window=params.fast_window, slow_window=params.slow_window,
            rsi_min=params.rsi_min, rsi_max=params.rsi_max, stop_loss=params.stop_loss,
            take_profit=params.take_profit, min_holding_days=params.min_holding_days,
            require_trend_confirmation=params.require_trend_confirmation,
            core_ratio=params.core_ratio, atr_multiple=params.atr_multiple,
        )
        rows.append({
            "fast": params.fast_window, "slow": params.slow_window,
            "rsi_min": params.rsi_min, "rsi_max": params.rsi_max,
            "stop_loss": params.stop_loss, "take_profit": params.take_profit,
            "return": result.total_return, "benchmark_return": result.benchmark_return,
            "excess_return": result.excess_return, "mdd": result.mdd,
            "sharpe": result.sharpe, "trades": result.trades,
        })
    details = pd.DataFrame(rows)
    positive = details["return"].gt(0).mean() * 100
    beat = details["excess_return"].gt(0).mean() * 100
    dispersion = details["return"].std(ddof=0)
    verdict = "안정" if positive >= 80 and beat >= 60 and dispersion <= max(abs(details["return"].median()), 1) else "민감"
    return SensitivityResult(
        round(positive, 2), round(beat, 2), round(details["return"].median(), 2),
        round(float(dispersion), 2), verdict, details,
    )


def monte_carlo_trades(result: BacktestResult, simulations: int = 5000, seed: int = 42) -> MonteCarloResult:
    if result.trade_log.empty:
        raise ValueError("몬테카를로 검증에 필요한 완료 거래가 없습니다.")
    returns = result.trade_log["return_pct"].to_numpy(dtype=float) / 100
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(simulations):
        sampled = rng.choice(returns, size=len(returns), replace=True)
        curve = np.cumprod(1 + sampled)
        total = (curve[-1] - 1) * 100
        running_max = np.maximum.accumulate(np.r_[1.0, curve])
        drawdowns = np.r_[1.0, curve] / running_max - 1
        rows.append((total, drawdowns.min() * 100))
    details = pd.DataFrame(rows, columns=["total_return", "mdd"])
    loss_probability = details["total_return"].lt(0).mean() * 100
    p05 = details["total_return"].quantile(.05)
    mdd_p05 = details["mdd"].quantile(.05)
    verdict = "안정" if p05 > 0 and loss_probability < 10 and mdd_p05 > -40 else "주의"
    return MonteCarloResult(
        simulations, round(details["total_return"].median(), 2), round(p05, 2),
        round(details["total_return"].quantile(.95), 2), round(loss_probability, 2),
        round(details["mdd"].median(), 2), round(mdd_p05, 2), verdict, details,
    )
