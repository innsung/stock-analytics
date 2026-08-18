import numpy as np
import pandas as pd

from src.backtest.engine import StrategyParams
from src.backtest.walk_forward import walk_forward_optimize


def test_walk_forward_keeps_test_period_out_of_training():
    dates = pd.bdate_range("2020-01-01", "2024-12-31")
    close = 100 + np.arange(len(dates)) * .05 + np.sin(np.arange(len(dates)) / 12) * 3
    data = pd.DataFrame({"date": dates, "open": close, "close": close, "volume": 1000})
    grid = [StrategyParams(10, 60, 0, 100, -.08, .20, 3, False)]
    result = walk_forward_optimize(data, train_years=2, test_months=12,
        parameter_grid=grid, minimum_train_trades=0, commission_pct=0, sell_tax_pct=0, slippage_pct=0)
    assert not result.folds.empty
    for row in result.folds.itertuples():
        assert pd.Timestamp(row.train_end) < pd.Timestamp(row.test_start)
    assert result.verdict in {"통과", "보류"}
