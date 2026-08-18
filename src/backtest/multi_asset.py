from dataclasses import dataclass, field
from datetime import timedelta
import math

import pandas as pd

from src.backtest.walk_forward import _run, _selection_score, default_parameter_grid


DEFAULT_INDUSTRIES = {
    "005930": "반도체", "000660": "반도체", "035420": "인터넷",
    "005380": "자동차", "051910": "화학", "105560": "금융",
}


@dataclass
class MultiAssetResult:
    portfolio_return: float
    portfolio_mdd: float
    portfolio_sharpe: float
    benchmark_return: float
    benchmark_mdd: float
    benchmark_sharpe: float
    verdict: str
    folds: pd.DataFrame = field(repr=False)
    stocks: pd.DataFrame = field(repr=False)
    industries: pd.DataFrame = field(repr=False)
    portfolio_curve: pd.DataFrame = field(repr=False)


def common_parameter_walk_forward(
    frames: dict[str, pd.DataFrame],
    industries: dict[str, str] | None = None,
    train_years: int = 2,
    test_months: int = 12,
    initial_capital: float = 10_000_000,
    commission_pct: float = .015,
    sell_tax_pct: float = .18,
    slippage_pct: float = .05,
) -> MultiAssetResult:
    if len(frames) < 2:
        raise ValueError("공통 파라미터 검증에는 최소 2개 종목이 필요합니다.")
    industries = {**DEFAULT_INDUSTRIES, **(industries or {})}
    all_dates = pd.concat([pd.to_datetime(frame["date"], format="mixed") for frame in frames.values()])
    start, finish = pd.Timestamp(all_dates.min()), pd.Timestamp(all_dates.max())
    train_start = start
    fold_rows, return_series, benchmark_series = [], [], []

    while True:
        train_end = train_start + pd.DateOffset(years=train_years) - timedelta(days=1)
        test_start = train_end + timedelta(days=1)
        test_end = min(test_start + pd.DateOffset(months=test_months) - timedelta(days=1), finish)
        if test_start >= finish:
            break
        candidate_rows = []
        for params in default_parameter_grid():
            scores = []
            for frame in frames.values():
                try:
                    trained = _run(frame, params, train_start, train_end, initial_capital,
                                   commission_pct, sell_tax_pct, slippage_pct)
                    scores.append(_selection_score(trained, 2))
                except ValueError:
                    pass
            if scores:
                candidate_rows.append((sum(scores) / len(scores), params))
        if not candidate_rows:
            raise ValueError("공통 학습구간에서 평가 가능한 조합이 없습니다.")
        _, best = max(candidate_rows, key=lambda item: item[0])
        fold_daily, fold_benchmark_daily = [], []
        for code, frame in frames.items():
            try:
                tested = _run(frame, best, test_start, test_end, initial_capital,
                              commission_pct, sell_tax_pct, slippage_pct)
            except ValueError:
                continue
            fold_rows.append({
                "fold_test_start": tested.start_date, "fold_test_end": tested.end_date,
                "code": code, "industry": industries.get(code, "미분류"),
                "fast": best.fast_window, "slow": best.slow_window,
                "rsi_min": best.rsi_min, "rsi_max": best.rsi_max,
                "stop_loss": best.stop_loss, "take_profit": best.take_profit,
                "return": tested.total_return, "benchmark_return": tested.benchmark_return,
                "excess_return": tested.excess_return, "mdd": tested.mdd,
                "sharpe": tested.sharpe, "trades": tested.trades,
            })
            daily = tested.equity_curve["strategy_equity"].pct_change().fillna(0).rename(code)
            fold_daily.append(daily)
            benchmark_daily = tested.equity_curve["benchmark_equity"].pct_change().fillna(0).rename(code)
            fold_benchmark_daily.append(benchmark_daily)
        if fold_daily:
            equal_weight = pd.concat(fold_daily, axis=1).mean(axis=1)
            return_series.append(equal_weight)
            benchmark_series.append(pd.concat(fold_benchmark_daily, axis=1).mean(axis=1))
        train_start += pd.DateOffset(months=test_months)
        if test_end >= finish:
            break

    folds = pd.DataFrame(fold_rows)
    if folds.empty:
        raise ValueError("공통 파라미터의 미사용구간 결과가 없습니다.")
    combined_returns = pd.concat(return_series).sort_index()
    combined_returns = combined_returns[~combined_returns.index.duplicated(keep="last")]
    curve = (1 + combined_returns).cumprod()
    mdd = (curve / curve.cummax() - 1).min() * 100
    std = combined_returns.std(ddof=0)
    sharpe = combined_returns.mean() / std * math.sqrt(252) if std > 0 else 0.0
    portfolio_return = (curve.iloc[-1] - 1) * 100
    combined_benchmark = pd.concat(benchmark_series).sort_index()
    combined_benchmark = combined_benchmark[~combined_benchmark.index.duplicated(keep="last")]
    benchmark_curve = (1 + combined_benchmark).cumprod()
    benchmark_portfolio_return = (benchmark_curve.iloc[-1] - 1) * 100
    benchmark_mdd = (benchmark_curve / benchmark_curve.cummax() - 1).min() * 100
    benchmark_std = combined_benchmark.std(ddof=0)
    benchmark_sharpe = combined_benchmark.mean() / benchmark_std * math.sqrt(252) if benchmark_std > 0 else 0.0

    stock_rows = []
    for code, group in folds.groupby("code"):
        stock_rows.append({
            "code": code, "industry": group["industry"].iloc[0],
            "oos_return": round((group["return"].div(100).add(1).prod() - 1) * 100, 2),
            "benchmark_return": round((group["benchmark_return"].div(100).add(1).prod() - 1) * 100, 2),
            "positive_fold_rate": round(group["return"].gt(0).mean() * 100, 2),
            "average_mdd": round(group["mdd"].mean(), 2), "average_sharpe": round(group["sharpe"].mean(), 2),
        })
    stocks = pd.DataFrame(stock_rows)
    industry_rows = []
    for industry, group in folds.groupby("industry"):
        by_fold = group.groupby(["fold_test_start", "fold_test_end"])[["return", "benchmark_return"]].mean()
        industry_rows.append({
            "industry": industry,
            "oos_return": round((by_fold["return"].div(100).add(1).prod() - 1) * 100, 2),
            "benchmark_return": round((by_fold["benchmark_return"].div(100).add(1).prod() - 1) * 100, 2),
            "stocks": group["code"].nunique(),
        })
    industry_frame = pd.DataFrame(industry_rows)
    benchmark_return = round(benchmark_portfolio_return, 2)
    verdict = "통과" if portfolio_return > benchmark_return and sharpe >= benchmark_sharpe and mdd >= benchmark_mdd else "보류"
    return MultiAssetResult(
        round(portfolio_return, 2), round(float(mdd), 2), round(float(sharpe), 2),
        benchmark_return, round(float(benchmark_mdd), 2), round(float(benchmark_sharpe), 2),
        verdict, folds, stocks, industry_frame,
        pd.DataFrame({"daily_return": combined_returns, "portfolio_equity": curve,
                      "benchmark_daily_return": combined_benchmark,
                      "benchmark_equity": benchmark_curve}),
    )
