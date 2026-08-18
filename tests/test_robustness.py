import numpy as np
import pandas as pd

from src.backtest.engine import run_ma_rsi_strategy
from src.backtest.robustness import monte_carlo_trades


def test_monte_carlo_is_reproducible():
    dates = pd.bdate_range("2020-01-01", periods=350)
    close = 100 + np.arange(len(dates)) * .08 + np.sin(np.arange(len(dates)) / 8) * 8
    data = pd.DataFrame({"date": dates, "open": close, "close": close, "rsi14": 55})
    result = run_ma_rsi_strategy(data, fast_window=10, slow_window=60,
                                  rsi_min=0, rsi_max=100, require_trend_confirmation=False)
    monte = monte_carlo_trades(result, simulations=100, seed=7)
    assert monte.simulations == 100
    assert len(monte.details) == 100
    assert monte.return_p05 <= monte.median_return <= monte.return_p95
