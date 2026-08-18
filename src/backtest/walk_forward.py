from dataclasses import dataclass, field
from datetime import timedelta
from itertools import product

import pandas as pd

from src.backtest.engine import BacktestResult, StrategyParams, run_ma_rsi_strategy


@dataclass
class WalkForwardResult:
    oos_return: float
    benchmark_return: float
    excess_return: float
    positive_fold_rate: float
    average_oos_sharpe: float
    average_degradation: float
    parameter_stability: float
    absolute_status: str
    benchmark_status: str
    risk_status: str
    stability_status: str
    verdict: str
    folds: pd.DataFrame = field(repr=False)


def default_parameter_grid() -> list[StrategyParams]:
    return [
        StrategyParams(fast, slow, rsi_min, rsi_max, stop, take, hold, True)
        for fast, slow, rsi_min, rsi_max, stop, take, hold in product(
            (10, 20), (60, 120), (40, 45), (68,), (-0.05, -0.08), (0.12, 0.20), (5,)
        ) if fast < slow
    ]


def _run(data, params, start, end, capital, commission, tax, slippage) -> BacktestResult:
    return run_ma_rsi_strategy(
        data, initial_capital=capital, commission_pct=commission, sell_tax_pct=tax,
        slippage_pct=slippage, evaluation_start=start, evaluation_end=end,
        fast_window=params.fast_window, slow_window=params.slow_window,
        rsi_min=params.rsi_min, rsi_max=params.rsi_max, stop_loss=params.stop_loss,
        take_profit=params.take_profit, min_holding_days=params.min_holding_days,
        require_trend_confirmation=params.require_trend_confirmation,
        core_ratio=params.core_ratio, atr_multiple=params.atr_multiple,
    )


def _selection_score(result: BacktestResult, minimum_trades: int) -> float:
    if result.trades < minimum_trades:
        return -10_000 + result.trades
    # 수익만 극대화하지 않고 변동성·낙폭·거래비용을 함께 벌점 처리한다.
    return (result.cagr + result.sharpe * 3 + result.mdd * 0.20
            + (result.cagr - result.benchmark_cagr) * .25 - result.total_cost / 1_000_000)


def walk_forward_optimize(
    data: pd.DataFrame,
    train_years: int = 2,
    test_months: int = 12,
    step_months: int = 12,
    initial_capital: float = 10_000_000,
    commission_pct: float = 0.015,
    sell_tax_pct: float = 0.18,
    slippage_pct: float = 0.05,
    parameter_grid: list[StrategyParams] | None = None,
    minimum_train_trades: int = 3,
) -> WalkForwardResult:
    dates = pd.to_datetime(data["date"], format="mixed")
    start, finish = pd.Timestamp(dates.min()), pd.Timestamp(dates.max())
    grid = parameter_grid or default_parameter_grid()
    fold_rows, selected = [], []
    train_start = start

    while True:
        train_end = train_start + pd.DateOffset(years=train_years) - timedelta(days=1)
        test_start = train_end + timedelta(days=1)
        test_end = min(test_start + pd.DateOffset(months=test_months) - timedelta(days=1), finish)
        if test_start >= finish:
            break
        candidates = []
        for params in grid:
            try:
                result = _run(data, params, train_start, train_end, initial_capital,
                              commission_pct, sell_tax_pct, slippage_pct)
                candidates.append((_selection_score(result, minimum_train_trades), params, result))
            except ValueError:
                continue
        if not candidates:
            raise ValueError("학습 구간에서 평가 가능한 전략 조합이 없습니다.")
        _, best, in_sample = max(candidates, key=lambda item: item[0])
        out_sample = _run(data, best, test_start, test_end, initial_capital,
                          commission_pct, sell_tax_pct, slippage_pct)
        selected.append(best)
        fold_rows.append({
            "train_start": train_start.strftime("%Y-%m-%d"), "train_end": train_end.strftime("%Y-%m-%d"),
            "test_start": out_sample.start_date, "test_end": out_sample.end_date,
            "fast": best.fast_window, "slow": best.slow_window, "rsi_min": best.rsi_min,
            "rsi_max": best.rsi_max, "stop_loss": best.stop_loss, "take_profit": best.take_profit,
            "min_hold": best.min_holding_days, "is_cagr": in_sample.cagr, "is_sharpe": in_sample.sharpe,
            "oos_return": out_sample.total_return, "oos_cagr": out_sample.cagr,
            "oos_mdd": out_sample.mdd, "oos_sharpe": out_sample.sharpe,
            "benchmark_return": out_sample.benchmark_return,
            "benchmark_mdd": out_sample.benchmark_mdd,
            "benchmark_sharpe": out_sample.benchmark_sharpe, "trades": out_sample.trades,
        })
        train_start += pd.DateOffset(months=step_months)
        if test_end >= finish:
            break

    if not fold_rows:
        raise ValueError("워크포워드에는 학습기간 이후의 테스트기간이 필요합니다.")
    folds = pd.DataFrame(fold_rows)
    oos = (folds["oos_return"].div(100).add(1).prod() - 1) * 100
    benchmark = (folds["benchmark_return"].div(100).add(1).prod() - 1) * 100
    positive_rate = folds["oos_return"].gt(0).mean() * 100
    degradation = (folds["oos_cagr"] - folds["is_cagr"]).mean()
    counts = pd.Series([str(params) for params in selected]).value_counts()
    stability = counts.iloc[0] / len(selected) * 100
    absolute_status = "통과" if oos > 0 and positive_rate >= 50 else "실패"
    benchmark_status = "통과" if oos > benchmark else "실패"
    risk_status = "통과" if folds["oos_sharpe"].mean() >= folds["benchmark_sharpe"].mean() and folds["oos_mdd"].mean() >= folds["benchmark_mdd"].mean() else "주의"
    stability_status = "통과" if stability >= 50 and degradation > -20 else "주의"
    verdict = "통과" if all(x == "통과" for x in (absolute_status, benchmark_status, risk_status, stability_status)) else ("조건부" if absolute_status == "통과" and risk_status == "통과" else "보류")
    return WalkForwardResult(
        oos_return=round(oos, 2), benchmark_return=round(benchmark, 2),
        excess_return=round(oos - benchmark, 2), positive_fold_rate=round(positive_rate, 2),
        average_oos_sharpe=round(folds["oos_sharpe"].mean(), 2),
        average_degradation=round(degradation, 2), parameter_stability=round(stability, 2),
        absolute_status=absolute_status, benchmark_status=benchmark_status,
        risk_status=risk_status, stability_status=stability_status,
        verdict=verdict, folds=folds,
    )
