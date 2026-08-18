import numpy as np
import pandas as pd

from src.backtest.engine import StrategyParams
from src.backtest.multi_asset import common_parameter_walk_forward


def test_common_parameters_create_portfolio_metrics(monkeypatch):
    dates = pd.bdate_range("2020-01-01", "2024-12-31")
    base = np.arange(len(dates))
    frames = {
        "AAA": pd.DataFrame({"date": dates, "open": 100 + base * .05,
                             "close": 100 + base * .05, "volume": 1000}),
        "BBB": pd.DataFrame({"date": dates, "open": 80 + base * .03 + np.sin(base / 20),
                             "close": 80 + base * .03 + np.sin(base / 20), "volume": 900}),
    }
    monkeypatch.setattr("src.backtest.multi_asset.default_parameter_grid",
                        lambda: [StrategyParams(10, 60, 0, 100, -.08, .20, 5, False)])
    result = common_parameter_walk_forward(frames, {"AAA": "A업", "BBB": "B업"})
    assert set(result.stocks["code"]) == {"AAA", "BBB"}
    assert set(result.industries["industry"]) == {"A업", "B업"}
    assert isinstance(result.portfolio_mdd, float)
    assert isinstance(result.portfolio_sharpe, float)
