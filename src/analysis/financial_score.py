from dataclasses import asdict, dataclass
import sqlite3


# OpenDART의 IFRS 표준 계정 ID를 우선 사용한다. 회사별 확장 계정은 이름을
# 보조 수단으로만 사용하며, 반드시 올바른 재무제표 구분 안에서 찾는다.
ACCOUNT_RULES = {
    "revenue": {
        "statements": {"IS", "CIS"},
        "ids": ("ifrs-full_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"),
        "names": ("매출액", "영업수익", "수익(매출액)"),
    },
    "operating_income": {
        "statements": {"IS", "CIS"},
        "ids": ("dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"),
        "names": ("영업이익", "영업이익(손실)"),
    },
    "net_income": {
        "statements": {"IS", "CIS"},
        "ids": ("ifrs-full_ProfitLoss",),
        "names": ("당기순이익", "당기순이익(손실)", "연결당기순이익"),
    },
    "assets": {
        "statements": {"BS"}, "ids": ("ifrs-full_Assets",), "names": ("자산총계",),
    },
    "liabilities": {
        "statements": {"BS"}, "ids": ("ifrs-full_Liabilities",), "names": ("부채총계",),
    },
    "equity": {
        "statements": {"BS"},
        "ids": ("ifrs-full_Equity", "ifrs-full_EquityAttributableToOwnersOfParent"),
        "names": ("자본총계",),
    },
    "operating_cash_flow": {
        "statements": {"CF"},
        "ids": ("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
        "names": ("영업활동으로 인한 현금흐름", "영업활동현금흐름"),
    },
}


@dataclass(frozen=True)
class FinancialAnalysis:
    fiscal_year: int
    revenue: float | None
    operating_income: float | None
    net_income: float | None
    assets: float | None
    liabilities: float | None
    equity: float | None
    operating_cash_flow: float | None
    revenue_growth: float | None
    operating_margin: float | None
    roe: float | None
    debt_ratio: float | None
    score: float
    warnings: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator * 100, 6)


def _normalize(text: str) -> str:
    return text.replace(" ", "").replace("_", "").lower()


def _pick(rows: list[sqlite3.Row], key: str) -> float | None:
    rule = ACCOUNT_RULES[key]
    candidates = [row for row in rows if row["sj_div"] in rule["statements"]]
    for account_id in rule["ids"]:
        for row in candidates:
            if row["account_id"] == account_id and row["amount"] is not None:
                return float(row["amount"])
    names = {_normalize(name) for name in rule["names"]}
    for row in candidates:
        if _normalize(row["account_name"]) in names and row["amount"] is not None:
            return float(row["amount"])
    return None


def financial_score(revenue_growth, operating_margin, debt_ratio, roe=None, operating_cash_flow=None) -> float:
    growth = 50 if revenue_growth is None else max(0, min(100, 50 + revenue_growth * 2))
    margin = 50 if operating_margin is None else max(0, min(100, 40 + operating_margin * 3))
    debt = 50 if debt_ratio is None else max(0, min(100, 100 - debt_ratio / 2))
    roe_score = 50 if roe is None else max(0, min(100, 40 + roe * 3))
    cash = 50 if operating_cash_flow is None else (75 if operating_cash_flow > 0 else 20)
    return round(growth * .20 + margin * .25 + debt * .20 + roe_score * .20 + cash * .15, 2)


def analyze_financials(conn: sqlite3.Connection, code: str, as_of: str | None = None) -> FinancialAnalysis | None:
    conn.row_factory = sqlite3.Row
    disclosure_filter = " AND (disclosed_at IS NULL OR disclosed_at<=?)" if as_of else ""
    params = (code, as_of) if as_of else (code,)
    latest_row = conn.execute(
        "SELECT MAX(fiscal_year) AS year FROM financial_statements WHERE code=? AND report_code='11011' AND fs_div='CFS'" + disclosure_filter,
        params,
    ).fetchone()
    latest = latest_row["year"] if latest_row else None
    if latest is None:
        return None

    def rows_for(year: int) -> list[sqlite3.Row]:
        row_params = (code, year, as_of) if as_of else (code, year)
        return conn.execute(
            """SELECT fs_div,sj_div,account_id,account_name,amount
               FROM financial_statements
               WHERE code=? AND fiscal_year=? AND report_code='11011' AND fs_div='CFS'
            """ + disclosure_filter + " ORDER BY account_order", row_params,
        ).fetchall()

    current, previous = rows_for(latest), rows_for(latest - 1)
    values = {key: _pick(current, key) for key in ACCOUNT_RULES}
    previous_revenue = _pick(previous, "revenue")
    previous_equity = _pick(previous, "equity")
    growth = None
    if previous_revenue not in (None, 0) and values["revenue"] is not None:
        growth = round((values["revenue"] / previous_revenue - 1) * 100, 6)
    margin = _ratio(values["operating_income"], values["revenue"])
    average_equity = values["equity"]
    if values["equity"] is not None and previous_equity is not None:
        average_equity = (values["equity"] + previous_equity) / 2
    roe = _ratio(values["net_income"], average_equity)
    debt_ratio = _ratio(values["liabilities"], values["equity"])

    warnings = []
    missing = [key for key, value in values.items() if value is None]
    if missing:
        warnings.append("누락 계정: " + ", ".join(missing))
    if roe is not None and not -100 <= roe <= 100:
        warnings.append("ROE가 검증 범위를 벗어났습니다.")
    if debt_ratio is not None and not 0 <= debt_ratio <= 1000:
        warnings.append("부채비율이 검증 범위를 벗어났습니다.")
    score = financial_score(growth, margin, debt_ratio, roe, values["operating_cash_flow"])
    return FinancialAnalysis(
        fiscal_year=latest, revenue_growth=growth, operating_margin=margin, roe=roe,
        debt_ratio=debt_ratio, score=score, warnings=tuple(warnings), **values,
    )


def technical_score(latest) -> float:
    score = 50.0
    close = latest.get("close")
    for moving_average, weight in (("ma5", 7), ("ma20", 10), ("ma60", 13)):
        value = latest.get(moving_average)
        if value is not None and value == value:
            score += weight if close >= value else -weight
    rsi = latest.get("rsi14")
    if rsi is not None and rsi == rsi:
        if 45 <= rsi <= 65:
            score += 5
        elif rsi >= 75:
            score -= 10
        elif rsi <= 25:
            score -= 5
    return round(max(0, min(100, score)), 2)


def investment_opinion(score: float) -> str:
    if score >= 70: return "긍정"
    if score >= 55: return "관심"
    if score >= 40: return "중립"
    return "주의"
