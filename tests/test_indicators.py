import pandas as pd

from src.analysis.indicators import add_indicators


def test_indicators_are_added():
    frame = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=70), "close": range(100, 170), "volume": range(1000, 1070)})
    result = add_indicators(frame)
    assert {"ma5", "ma20", "ma60", "rsi14", "volume_change"}.issubset(result.columns)
    assert result.iloc[-1]["ma60"] > 0

