import pandas as pd

from src.backtest.engine import run_ma_rsi_strategy


def test_backtest_uses_previous_signal_and_next_open():
    data = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=4),
        "open": [90, 100, 100, 110], "close": [90, 100, 112, 110],
        "rsi14": [60, 60, 60, 60],
    })
    result = run_ma_rsi_strategy(
        data, initial_capital=10_000, commission_pct=0, sell_tax_pct=0, slippage_pct=0,
        fast_window=1, slow_window=2, rsi_min=0, rsi_max=100,
        min_holding_days=0, require_trend_confirmation=False,
    )
    assert result.trades == 1
    assert result.total_return == 10.0
    assert result.trade_log.iloc[0]["entry_date"] == "2025-01-03"
    assert result.trade_log.iloc[0]["exit_date"] == "2025-01-04"
    assert isinstance(result.benchmark_mdd, float)
    assert isinstance(result.benchmark_sharpe, float)
    assert not result.yearly_performance.empty


def test_backtest_deducts_costs_and_calculates_benchmark():
    data = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=4),
        "open": [90, 100, 100, 110], "close": [90, 100, 112, 110],
        "rsi14": [60, 60, 60, 60],
    })
    kwargs = dict(fast_window=1, slow_window=2, rsi_min=0, rsi_max=100,
                  min_holding_days=0, require_trend_confirmation=False)
    free = run_ma_rsi_strategy(data, initial_capital=10_000, commission_pct=0, sell_tax_pct=0, slippage_pct=0, **kwargs)
    realistic = run_ma_rsi_strategy(data, initial_capital=10_000, commission_pct=.015, sell_tax_pct=.18, slippage_pct=.05, **kwargs)
    assert realistic.total_return < free.total_return
    assert realistic.total_cost > 0
    assert isinstance(realistic.benchmark_return, float)
