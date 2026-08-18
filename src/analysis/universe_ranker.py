import sqlite3
from datetime import date, datetime

import numpy as np
import pandas as pd

from src.analysis.financial_score import analyze_financials


def _pct_score(series: pd.Series, higher_is_better=True) -> pd.Series:
    valid = pd.to_numeric(series, errors="coerce")
    valid = valid.mask(~np.isfinite(valid), np.nan)
    # 높은 값 우대는 오름차순 백분위, 낮은 값 우대는 내림차순 백분위를 쓴다.
    # 두 경우 모두 우수한 값이 100점 방향이 된다.
    score = valid.rank(pct=True, ascending=higher_is_better) * 100
    return score.fillna(50).clip(0, 100)


def rank_universe(conn: sqlite3.Connection, codes: list[str], industries: dict[str, str],
                  benchmark_code: str = "069500", min_liquidity: float = 1_000_000_000) -> pd.DataFrame:
    benchmark = pd.read_sql_query("SELECT date,close FROM stock_prices WHERE code=? ORDER BY date",
                                  conn, params=(benchmark_code,))
    benchmark_63 = benchmark["close"].iloc[-1] / benchmark["close"].iloc[-64] - 1 if len(benchmark) >= 64 else 0
    rows = []
    for code in codes:
        prices = pd.read_sql_query("SELECT date,close,volume FROM stock_prices WHERE code=? ORDER BY date",
                                   conn, params=(code,))
        if len(prices) < 127:
            continue
        latest_valuation = conn.execute("""SELECT snapshot_date,price,market_cap,per,pbr,eps,bps,dividend_yield
            FROM valuation_snapshots WHERE code=? ORDER BY snapshot_date DESC LIMIT 1""", (code,)).fetchone()
        valuation = latest_valuation or (None,) * 8
        valuation_date = valuation[0]
        age_days = None
        if valuation_date:
            age_days = (date.today() - datetime.strptime(valuation_date, "%Y%m%d").date()).days
        valuation_complete = all(valuation[index] is not None for index in (3, 4, 5, 6))
        financial = analyze_financials(conn, code, valuation[0])
        returns = prices["close"].pct_change()
        return_63 = prices["close"].iloc[-1] / prices["close"].iloc[-64] - 1
        return_126 = prices["close"].iloc[-1] / prices["close"].iloc[-127] - 1
        vol60 = returns.tail(60).std() * np.sqrt(252)
        drawdown = prices["close"].iloc[-1] / prices["close"].tail(126).max() - 1
        rows.append({
            "code": code, "industry": industries.get(code, "미분류"),
            "price": valuation[1] or float(prices["close"].iloc[-1]), "market_cap": valuation[2],
            "per": valuation[3], "pbr": valuation[4], "eps": valuation[5], "bps": valuation[6],
            "dividend_yield": valuation[7],
            "valuation_date": valuation_date,
            "valuation_age_days": age_days,
            "valuation_status": ("누락" if not valuation_date else
                                 "일부 누락" if not valuation_complete else
                                 "오래됨" if age_days is not None and age_days > 7 else "정상"),
            "earnings_yield": (100 / valuation[3]) if valuation[3] and valuation[3] > 0 else None,
            "earnings_status": ("누락" if valuation[3] is None else
                                "적자" if valuation[3] <= 0 else "흑자"),
            "roe": financial.roe if financial else None,
            "net_income": financial.net_income if financial else None,
            "operating_margin": financial.operating_margin if financial else None,
            "revenue_growth": financial.revenue_growth if financial else None,
            "debt_ratio": financial.debt_ratio if financial else None,
            "cash_positive": 1 if financial and financial.operating_cash_flow and financial.operating_cash_flow > 0 else 0,
            "return_3m": return_63 * 100, "return_6m": return_126 * 100,
            "relative_3m": (return_63 - benchmark_63) * 100,
            "volatility_60": vol60 * 100, "drawdown_6m": drawdown * 100,
            "liquidity": float((prices["close"] * prices["volume"]).tail(20).mean()),
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    quality_parts = pd.DataFrame({
        "roe": _pct_score(frame["roe"]), "margin": _pct_score(frame["operating_margin"]),
        "growth": _pct_score(frame["revenue_growth"]), "debt": _pct_score(frame["debt_ratio"], False),
        "cash": frame["cash_positive"] * 100,
    })
    frame["quality_score"] = quality_parts.mean(axis=1)
    # 금융업은 예금이 부채로 잡히고 제조업식 영업이익률·부채비율 비교가 왜곡되므로
    # ROE, 성장성, 순이익 흑자 여부 중심의 공통 평가식을 사용한다.
    finance_mask = frame["industry"].str.contains("금융|은행|증권|보험", regex=True, na=False)
    if finance_mask.any():
        profitable = pd.to_numeric(frame["net_income"], errors="coerce").gt(0).astype(float)
        finance_quality = (_pct_score(frame["roe"]) * .60 +
                           _pct_score(frame["revenue_growth"]) * .20 +
                           profitable * 100 * .20)
        frame.loc[finance_mask, "quality_score"] = finance_quality.loc[finance_mask]
    frame["quality_model"] = np.where(finance_mask, "금융업", "일반업종")
    value_scores = pd.Series(0.0, index=frame.index)
    frame["valuation_reference"] = ""
    frame["per_peer_count"] = 0
    frame["pbr_peer_count"] = 0
    positive_per = frame["per"].where(frame["per"] > 0)
    positive_pbr = frame["pbr"].where(frame["pbr"] > 0)
    valid_dividend = frame["dividend_yield"].where(frame["dividend_yield"] >= 0)
    for _, indices in frame.groupby("industry").groups.items():
        per_industry_count = int(positive_per.loc[indices].notna().sum())
        pbr_industry_count = int(positive_pbr.loc[indices].notna().sum())
        dividend_industry_count = int(valid_dividend.loc[indices].notna().sum())
        per_reference = indices if per_industry_count >= 3 else frame.index
        pbr_reference = indices if pbr_industry_count >= 3 else frame.index
        dividend_reference = indices if dividend_industry_count >= 3 else frame.index
        per_score = _pct_score(positive_per.loc[per_reference], False).reindex(indices).fillna(50)
        pbr_score = _pct_score(positive_pbr.loc[pbr_reference], False).reindex(indices).fillna(50)
        dividend_score = _pct_score(valid_dividend.loc[dividend_reference]).reindex(indices).fillna(50)
        value_scores.loc[indices] = per_score * .45 + pbr_score * .35 + dividend_score * .20
        frame.loc[indices, "per_peer_count"] = int(positive_per.loc[per_reference].notna().sum())
        frame.loc[indices, "pbr_peer_count"] = int(positive_pbr.loc[pbr_reference].notna().sum())
        frame.loc[indices, "valuation_reference"] = (
            ("PER:업종" if per_industry_count >= 3 else "PER:전체") + "/" +
            ("PBR:업종" if pbr_industry_count >= 3 else "PBR:전체")
        )
    frame["value_score"] = value_scores.fillna(50)
    frame["momentum_score"] = (_pct_score(frame["relative_3m"]) * .45 +
                               _pct_score(frame["return_6m"]) * .35 +
                               _pct_score(frame["return_3m"]) * .20)
    frame["risk_score"] = (_pct_score(frame["volatility_60"], False) * .60 +
                           _pct_score(frame["drawdown_6m"]) * .40)
    valuation_fields = ["per", "pbr", "eps", "bps"]
    frame["data_confidence"] = (frame[valuation_fields].notna().mean(axis=1) * 40 +
                                frame[["roe", "operating_margin", "revenue_growth", "debt_ratio"]]
                                .notna().mean(axis=1) * 40 + 20)
    frame["financial_status"] = np.select(
        [frame["data_confidence"] >= 100, frame["data_confidence"] >= 80],
        ["완전", "일부 누락"], default="부족")
    frame["data_warning"] = ""
    frame.loc[frame["earnings_status"] == "적자", "data_warning"] = "적자 PER 제외"
    stale = frame["valuation_age_days"].fillna(9999) > 7
    frame.loc[stale, "data_warning"] = frame.loc[stale, "data_warning"].apply(
        lambda value: " | ".join(filter(None, [value, "가치지표 7일 초과"])))
    reasons = pd.Series("", index=frame.index, dtype="object")
    conditions = [
        (frame["earnings_status"] != "흑자", "적자 또는 PER 누락"),
        (pd.to_numeric(frame["roe"], errors="coerce").fillna(0.0) <= 0,
         "ROE 0% 이하 또는 누락"),
        (frame["data_confidence"] < 80, "데이터 신뢰도 80 미만"),
        (frame["liquidity"] < min_liquidity, "20일 평균 거래대금 부족"),
    ]
    for condition, label in conditions:
        reasons.loc[condition] = reasons.loc[condition].apply(
            lambda value: " | ".join(filter(None, [value, label])))
    frame["eligible"] = reasons.eq("")
    frame["ineligible_reason"] = reasons
    frame["total_score"] = (frame["quality_score"] * .30 + frame["value_score"] * .25 +
                            frame["momentum_score"] * .25 + frame["risk_score"] * .20)
    return frame.sort_values("total_score", ascending=False).reset_index(drop=True)
