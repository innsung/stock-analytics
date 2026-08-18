import numpy as np
import pandas as pd

from src.backtest.realistic_portfolio import run_lockbox


def make_frame(dates, start, slope, phase=0):
    x = np.arange(len(dates))
    close = start + x * slope + np.sin(x / 15 + phase) * 3
    return pd.DataFrame({"date": dates, "open": close * .999, "high": close * 1.01,
                         "low": close * .99, "close": close, "volume": 1000})


def test_realistic_portfolio_has_lockbox_and_integer_trades():
    dates = pd.bdate_range("2020-01-01", "2025-12-31")
    frames = {"AAA": make_frame(dates, 100, .04), "BBB": make_frame(dates, 80, .03, 1),
              "CCC": make_frame(dates, 60, .02, 2)}
    benchmark = make_frame(dates, 90, .025, .5)
    result = run_lockbox(frames, benchmark, {"AAA": "기술", "BBB": "기술", "CCC": "산업"},
                         lockbox_months=12, initial_capital=10_000_000,
                         stock_cap=.40, sector_cap=.70)
    assert result.development.end_date < result.lockbox.start_date
    assert not result.lockbox.equity_curve.empty
    assert result.lockbox.trade_log["quantity"].map(lambda value: float(value).is_integer()).all()
    assert isinstance(result.lockbox.mdd, float)
    assert isinstance(result.lockbox.benchmark_sharpe, float)
    assert result.lockbox.allocation_log["target_total_weight"].max() <= .400001
    sector_weights = result.lockbox.allocation_log.groupby(["date", "industry"])["target_total_weight"].sum()
    assert sector_weights.max() <= .700001
