import pandas as pd


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.sort_values("date").copy()
    data["ma5"] = data["close"].rolling(5).mean()
    data["ma20"] = data["close"].rolling(20).mean()
    data["ma60"] = data["close"].rolling(60).mean()
    delta = data["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    data["rsi14"] = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))
    data.loc[(loss == 0) & (gain > 0), "rsi14"] = 100
    data.loc[(gain == 0) & (loss > 0), "rsi14"] = 0
    data.loc[(gain == 0) & (loss == 0), "rsi14"] = 50
    data["volume_change"] = data["volume"].pct_change()
    return data
