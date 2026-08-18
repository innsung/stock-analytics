from __future__ import annotations

from datetime import datetime, timezone
import math
import sqlite3

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "return_5", "return_20", "return_60", "return_126",
    "relative_20", "relative_60", "volatility_20", "volatility_60",
    "rsi_14", "atr_14_pct", "ma_20_gap", "ma_60_gap", "liquidity_20",
    "benchmark_return_20", "benchmark_ma_120_gap", "benchmark_volatility_60",
    "market_regime", "revenue_growth", "operating_margin", "roe", "debt_ratio",
    "operating_cash_flow_positive", "reported_eps", "estimated_bps",
    "historical_per", "historical_pbr",
]

FEATURE_DB_COLUMNS = [
    "code", "feature_date", "benchmark_code", "industry", "close", "volume",
    *FEATURE_COLUMNS,
    "financial_fiscal_year", "financial_disclosed_at", "valuation_per",
    "financial_fs_div",
    "valuation_pbr", "valuation_eps", "valuation_bps", "valuation_snapshot_date",
    "valuation_known_at", "generated_at",
]

ACCOUNT_RULES = {
    "revenue": (
        ("ifrs-full_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"),
        ("매출액", "영업수익", "수익(매출액)"), {"IS", "CIS"}),
    "operating_income": (
        ("dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"),
        ("영업이익", "영업이익(손실)"), {"IS", "CIS"}),
    "net_income": (("ifrs-full_ProfitLoss",),
                   ("당기순이익", "당기순이익(손실)", "연결당기순이익"), {"IS", "CIS"}),
    "assets": (("ifrs-full_Assets",), ("자산총계",), {"BS"}),
    "liabilities": (("ifrs-full_Liabilities",), ("부채총계",), {"BS"}),
    "equity": (("ifrs-full_Equity", "ifrs-full_EquityAttributableToOwnersOfParent"),
               ("자본총계",), {"BS"}),
    "operating_cash_flow": (("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
                            ("영업활동으로인한현금흐름", "영업활동현금흐름"), {"CF"}),
    "eps": (("ifrs-full_BasicEarningsLossPerShare", "ifrs-full_DilutedEarningsLossPerShare"),
            ("기본주당이익", "기본주당이익(손실)", "주당이익"), {"IS", "CIS"}),
}


def _normalize(value: object) -> str:
    return str(value or "").replace(" ", "").replace("_", "").lower()


def _pick(group: pd.DataFrame, key: str) -> float | None:
    ids, names, statements = ACCOUNT_RULES[key]
    candidates = group[group["sj_div"].isin(statements)]
    for account_id in ids:
        rows = candidates[candidates["account_id"] == account_id]
        values = pd.to_numeric(rows["amount"], errors="coerce").dropna()
        if not values.empty:
            return float(values.iloc[0])
    normalized_names = {_normalize(name) for name in names}
    rows = candidates[candidates["account_name"].map(_normalize).isin(normalized_names)]
    values = pd.to_numeric(rows["amount"], errors="coerce").dropna()
    return None if values.empty else float(values.iloc[0])


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * 100


def point_in_time_annual_financials(conn: sqlite3.Connection, code: str) -> pd.DataFrame:
    """Build annual financial facts keyed by the date investors could first know them."""
    raw = pd.read_sql_query(
        """SELECT fiscal_year,disclosed_at,fs_div,sj_div,account_id,account_name,amount
           FROM financial_statements
           WHERE code=? AND report_code='11011' AND fs_div IN ('CFS','OFS')
             AND disclosed_at IS NOT NULL AND disclosed_at<>''
           ORDER BY fiscal_year,CASE fs_div WHEN 'CFS' THEN 0 ELSE 1 END,account_order""",
        conn, params=(code,))
    if raw.empty:
        return pd.DataFrame()
    raw["disclosed_at"] = raw["disclosed_at"].astype(str).str.replace("-", "", regex=False)
    # 연도별 CFS가 하나라도 있으면 CFS만, 없으면 OFS만 사용한다.
    preferred = raw.groupby("fiscal_year")["fs_div"].agg(
        lambda values: "CFS" if values.eq("CFS").any() else "OFS"
    )
    raw = raw[raw["fs_div"].eq(raw["fiscal_year"].map(preferred))]

    summaries: list[dict] = []
    for (year, disclosed_at), group in raw.groupby(["fiscal_year", "disclosed_at"], sort=True):
        values = {key: _pick(group, key) for key in ACCOUNT_RULES}
        summaries.append({"financial_fiscal_year": int(year),
                          "financial_disclosed_at": disclosed_at,
                          "financial_fs_div": preferred.loc[year], **values})
    facts = pd.DataFrame(summaries).sort_values(
        ["financial_fiscal_year", "financial_disclosed_at"]).drop_duplicates(
            "financial_fiscal_year", keep="first")
    by_year = facts.set_index("financial_fiscal_year")
    rows = []
    for row in facts.to_dict("records"):
        previous = by_year.loc[row["financial_fiscal_year"] - 1] if row["financial_fiscal_year"] - 1 in by_year.index else None
        previous_revenue = None if previous is None else previous["revenue"]
        previous_equity = None if previous is None else previous["equity"]
        revenue_growth = None
        if previous_revenue not in (None, 0) and pd.notna(previous_revenue) and row["revenue"] is not None:
            revenue_growth = round((row["revenue"] / float(previous_revenue) - 1) * 100, 10)
        average_equity = row["equity"]
        if row["equity"] is not None and previous_equity is not None and pd.notna(previous_equity):
            average_equity = (row["equity"] + float(previous_equity)) / 2
        shares = None
        if row["eps"] not in (None, 0) and row["net_income"] not in (None, 0):
            implied = row["net_income"] / row["eps"]
            if implied > 0:
                shares = implied
        estimated_bps = row["equity"] / shares if shares and row["equity"] is not None else None
        rows.append({
            "financial_fiscal_year": row["financial_fiscal_year"],
            "financial_disclosed_at": row["financial_disclosed_at"],
            "financial_fs_div": row["financial_fs_div"],
            "revenue_growth": revenue_growth,
            "operating_margin": _ratio(row["operating_income"], row["revenue"]),
            "roe": _ratio(row["net_income"], average_equity),
            "debt_ratio": _ratio(row["liabilities"], row["equity"]),
            "operating_cash_flow_positive": (None if row["operating_cash_flow"] is None
                                               else float(row["operating_cash_flow"] > 0)),
            "reported_eps": row["eps"], "estimated_bps": estimated_bps,
        })
    return pd.DataFrame(rows).sort_values("financial_disclosed_at")


def _technical_frame(prices: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    data = prices.sort_values("date").copy()
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    data["volume"] = pd.to_numeric(data["volume"], errors="coerce")
    returns = data["close"].pct_change()
    for period in (5, 20, 60, 126):
        data[f"return_{period}"] = data["close"].pct_change(period) * 100
    data["volatility_20"] = returns.rolling(20).std() * math.sqrt(252) * 100
    data["volatility_60"] = returns.rolling(60).std() * math.sqrt(252) * 100
    delta = data["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    data["rsi_14"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    data.loc[(loss == 0) & (gain > 0), "rsi_14"] = 100
    previous_close = data["close"].shift(1)
    true_range = pd.concat([(data["high"] - data["low"]).abs(),
                            (data["high"] - previous_close).abs(),
                            (data["low"] - previous_close).abs()], axis=1).max(axis=1)
    data["atr_14_pct"] = true_range.rolling(14).mean() / data["close"] * 100
    data["ma_20_gap"] = (data["close"] / data["close"].rolling(20).mean() - 1) * 100
    data["ma_60_gap"] = (data["close"] / data["close"].rolling(60).mean() - 1) * 100
    data["liquidity_20"] = (data["close"] * data["volume"]).rolling(20).mean()

    market = benchmark.sort_values("date")[["date", "close"]].rename(columns={"close": "benchmark_close"})
    market["benchmark_return_20"] = market["benchmark_close"].pct_change(20) * 100
    market["benchmark_return_60"] = market["benchmark_close"].pct_change(60) * 100
    market["benchmark_ma_120_gap"] = (
        market["benchmark_close"] / market["benchmark_close"].rolling(120).mean() - 1) * 100
    market["benchmark_volatility_60"] = (
        market["benchmark_close"].pct_change().rolling(60).std() * math.sqrt(252) * 100)
    data = data.merge(market, on="date", how="left")
    data["relative_20"] = data["return_20"] - data["benchmark_return_20"]
    data["relative_60"] = data["return_60"] - data["benchmark_return_60"]
    data["market_regime"] = np.select(
        [data["benchmark_ma_120_gap"] > 3, data["benchmark_ma_120_gap"] < -3], [1, -1], default=0)
    return data


def build_code_features(
    conn: sqlite3.Connection,
    code: str,
    industry: str,
    benchmark_code: str,
    benchmark: pd.DataFrame | None = None,
) -> pd.DataFrame:
    prices = pd.read_sql_query(
        "SELECT date,open,high,low,close,volume FROM stock_prices WHERE code=? ORDER BY date",
        conn, params=(code,))
    if benchmark is None:
        benchmark = pd.read_sql_query(
            "SELECT date,close FROM stock_prices WHERE code=? ORDER BY date", conn,
            params=(benchmark_code,))
    if len(prices) < 127 or len(benchmark) < 127:
        return pd.DataFrame()
    data = _technical_frame(prices, benchmark)
    data = data.rename(columns={"date": "feature_date"})
    data["_merge_date"] = pd.to_numeric(data["feature_date"], errors="raise")
    financials = point_in_time_annual_financials(conn, code)
    if not financials.empty:
        financials = financials.assign(
            _financial_merge_date=pd.to_numeric(financials["financial_disclosed_at"], errors="raise"))
        data = pd.merge_asof(data.sort_values("_merge_date"), financials,
                             left_on="_merge_date", right_on="_financial_merge_date",
                             direction="backward")
        data = data.drop(columns=["_financial_merge_date"])
    else:
        for column in ("revenue_growth", "operating_margin", "roe", "debt_ratio",
                       "operating_cash_flow_positive", "reported_eps", "estimated_bps",
                       "financial_fiscal_year", "financial_disclosed_at",
                       "financial_fs_div"):
            data[column] = np.nan
    valuations = pd.read_sql_query(
        """SELECT v.snapshot_date AS valuation_snapshot_date,COALESCE(m.known_at,v.snapshot_date) AS valuation_known_at,
                  v.per AS valuation_per,v.pbr AS valuation_pbr,v.eps AS valuation_eps,v.bps AS valuation_bps
           FROM valuation_snapshots v LEFT JOIN valuation_snapshot_meta m
             ON m.code=v.code AND m.snapshot_date=v.snapshot_date
           WHERE v.code=? ORDER BY v.snapshot_date""", conn, params=(code,))
    if not valuations.empty:
        valuations["_valuation_merge_date"] = pd.to_numeric(
            valuations["valuation_snapshot_date"], errors="raise")
        data = pd.merge_asof(data.sort_values("_merge_date"), valuations,
                             left_on="_merge_date", right_on="_valuation_merge_date",
                             direction="backward")
        data = data.drop(columns=["_valuation_merge_date"])
    else:
        for column in ("valuation_per", "valuation_pbr", "valuation_eps", "valuation_bps",
                       "valuation_snapshot_date", "valuation_known_at"):
            data[column] = np.nan
    data["historical_per"] = data["close"] / data["reported_eps"].replace(0, np.nan)
    data["historical_pbr"] = data["close"] / data["estimated_bps"].replace(0, np.nan)
    data["code"] = code
    data["benchmark_code"] = benchmark_code
    data["industry"] = industry
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data = data.drop(columns=["_merge_date"])
    return data.dropna(subset=["return_126", "benchmark_ma_120_gap"])[FEATURE_DB_COLUMNS]


def build_labels(prices: pd.DataFrame, benchmark: pd.DataFrame, code: str,
                 benchmark_code: str, horizons=(5, 20, 60)) -> pd.DataFrame:
    data = prices.sort_values("date")[["date", "close"]].merge(
        benchmark.sort_values("date")[["date", "close"]].rename(columns={"close": "benchmark_close"}),
        on="date", how="left")
    generated_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    closes = data["close"].astype(float).to_numpy()
    benchmark_closes = data["benchmark_close"].astype(float).to_numpy()
    dates = data["date"].astype(str).to_numpy()
    for horizon in horizons:
        for index in range(0, len(data) - horizon):
            if not np.isfinite(benchmark_closes[index]) or not np.isfinite(benchmark_closes[index + horizon]):
                continue
            future_return = closes[index + horizon] / closes[index] - 1
            benchmark_return = benchmark_closes[index + horizon] / benchmark_closes[index] - 1
            path = closes[index + 1:index + horizon + 1] / closes[index] - 1
            excess = future_return - benchmark_return
            rows.append({
                "code": code, "feature_date": dates[index], "benchmark_code": benchmark_code,
                "horizon": horizon, "forward_return": future_return * 100,
                "benchmark_forward_return": benchmark_return * 100,
                "excess_return": excess * 100, "positive_excess": int(excess > 0),
                "max_drawdown": float(np.min(path) * 100),
                "label_available_at": dates[index + horizon], "generated_at": generated_at,
            })
    return pd.DataFrame(rows)


def _sqlite_value(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)) or pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def _upsert_frame(conn: sqlite3.Connection, table: str, frame: pd.DataFrame,
                  columns: list[str]) -> int:
    if frame.empty:
        return 0
    placeholders = ",".join("?" for _ in columns)
    updates = ",".join(f"{column}=excluded.{column}" for column in columns
                       if column not in {"code", "feature_date", "benchmark_code", "horizon"})
    sql = f"INSERT INTO {table}({','.join(columns)}) VALUES({placeholders}) ON CONFLICT DO UPDATE SET {updates}"
    conn.executemany(sql, [tuple(_sqlite_value(value) for value in row)
                           for row in frame[columns].itertuples(index=False, name=None)])
    conn.commit()
    return len(frame)


def build_feature_store(conn: sqlite3.Connection, codes: list[str], industries: dict[str, str],
                        benchmark_code: str = "069500", horizons=(5, 20, 60)) -> tuple[int, int]:
    benchmark = pd.read_sql_query(
        "SELECT date,close FROM stock_prices WHERE code=? ORDER BY date", conn,
        params=(benchmark_code,))
    if benchmark.empty:
        raise ValueError(f"벤치마크 {benchmark_code} 가격 데이터가 없습니다.")
    feature_count = label_count = 0
    for code in codes:
        features = build_code_features(
            conn,
            code,
            industries.get(code, "미분류"),
            benchmark_code,
            benchmark=benchmark,
        )
        prices = pd.read_sql_query(
            "SELECT date,close FROM stock_prices WHERE code=? ORDER BY date", conn, params=(code,))
        labels = build_labels(prices, benchmark, code, benchmark_code, horizons)
        feature_count += _upsert_frame(conn, "ml_features", features, FEATURE_DB_COLUMNS)
        label_columns = ["code", "feature_date", "benchmark_code", "horizon", "forward_return",
                         "benchmark_forward_return", "excess_return", "positive_excess",
                         "max_drawdown", "label_available_at", "generated_at"]
        label_count += _upsert_frame(conn, "ml_labels", labels, label_columns)
    return feature_count, label_count
