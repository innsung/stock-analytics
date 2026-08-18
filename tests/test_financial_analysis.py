from database.database import connect, upsert_financials
from src.analysis.financial_score import analyze_financials


IDS = {
    "매출액": ("IS", "ifrs-full_Revenue"),
    "영업이익": ("IS", "dart_OperatingIncomeLoss"),
    "당기순이익": ("IS", "ifrs-full_ProfitLoss"),
    "자산총계": ("BS", "ifrs-full_Assets"),
    "부채총계": ("BS", "ifrs-full_Liabilities"),
    "자본총계": ("BS", "ifrs-full_Equity"),
    "영업활동으로 인한 현금흐름": ("CF", "ifrs-full_CashFlowsFromUsedInOperatingActivities"),
}


def rows(year, values):
    result = []
    for order, (name, amount) in enumerate(values.items()):
        sj_div, account_id = IDS[name]
        result.append(("005930", year, "11011", "CFS", sj_div, account_id,
                       name, amount, "KRW", order, f"{year + 1}0315", "DART"))
    return result


def test_financial_analysis_uses_standard_ids_and_average_equity(tmp_path):
    conn = connect(tmp_path / "test.db")
    upsert_financials(conn, rows(2024, {"매출액": 100, "영업이익": 10, "당기순이익": 8,
        "자산총계": 200, "부채총계": 80, "자본총계": 120, "영업활동으로 인한 현금흐름": 12}))
    upsert_financials(conn, rows(2025, {"매출액": 120, "영업이익": 18, "당기순이익": 12,
        "자산총계": 220, "부채총계": 88, "자본총계": 132, "영업활동으로 인한 현금흐름": 20}))
    # 같은 계정명이 다른 재무제표에 있어도 BS의 표준 계정이 선택돼야 한다.
    upsert_financials(conn, [("005930", 2025, "11011", "CFS", "SCE", "custom_Equity",
                              "자본총계", 3, "KRW", 999, "20260315", "DART")])
    result = analyze_financials(conn, "005930")
    assert result is not None
    assert result.revenue_growth == 20.0
    assert result.operating_margin == 15.0
    assert result.roe == 9.52381
    assert result.debt_ratio == 66.666667
    assert result.warnings == ()
    historical = analyze_financials(conn, "005930", "20251231")
    assert historical is not None
    assert historical.fiscal_year == 2024


def test_old_financial_table_is_preserved_as_legacy(tmp_path):
    db = tmp_path / "legacy.db"
    import sqlite3
    old = sqlite3.connect(db)
    old.execute("CREATE TABLE financial_statements(code TEXT, fiscal_year INTEGER, report_code TEXT, account_name TEXT, amount REAL, source TEXT)")
    old.execute("INSERT INTO financial_statements VALUES('005930',2025,'11011','자본총계',1,'DART')")
    old.commit(); old.close()
    conn = connect(db)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "financial_statements_legacy" in names
    assert "financial_statements" in names
