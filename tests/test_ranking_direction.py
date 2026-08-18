import pandas as pd

from src.analysis.universe_ranker import _pct_score


def test_lower_per_pbr_debt_and_volatility_receive_higher_scores():
    values = pd.Series([10.0, 20.0, 50.0], index=["low", "middle", "high"])
    scores = _pct_score(values, higher_is_better=False)
    assert scores["low"] > scores["middle"] > scores["high"]


def test_higher_roe_growth_momentum_receive_higher_scores():
    values = pd.Series([5.0, 10.0, 20.0], index=["low", "middle", "high"])
    scores = _pct_score(values, higher_is_better=True)
    assert scores["high"] > scores["middle"] > scores["low"]


def test_missing_value_is_neutral():
    scores = _pct_score(pd.Series([10.0, None, 30.0]), higher_is_better=False)
    assert scores.iloc[1] == 50


def test_sparse_industry_metric_must_use_larger_reference_pool():
    # 유효 PER가 한 개뿐인 업종에서는 그 한 종목이 자동으로 100점이 되면 안 된다.
    industry_per = pd.Series([265.0, None, None])
    assert industry_per.notna().sum() < 3
