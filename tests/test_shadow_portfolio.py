from datetime import date, timedelta

import pytest

from database.database import connect, upsert_financials, upsert_prices
from src.analysis.universe_ranker import rank_universe
from src.shadow.engine import run_shadow_day


def seed_prices(conn, code, start_price, slope):
    start = date(2025, 1, 1)
    rows = []
    for i in range(160):
        day = start + timedelta(days=i)
        price = start_price + i * slope
        rows.append((code, day.strftime("%Y%m%d"), price, price * 1.01, price * .99,
                     price, 10000, "TEST"))
    upsert_prices(conn, rows)


def seed_financials(conn, code):
    account_rows = []
    definitions = [
        ("IS", "ifrs-full_Revenue", "매출액", 100),
        ("IS", "dart_OperatingIncomeLoss", "영업이익", 15),
        ("IS", "ifrs-full_ProfitLoss", "당기순이익", 10),
        ("BS", "ifrs-full_Assets", "자산총계", 200),
        ("BS", "ifrs-full_Liabilities", "부채총계", 80),
        ("BS", "ifrs-full_Equity", "자본총계", 120),
        ("CF", "ifrs-full_CashFlowsFromUsedInOperatingActivities", "영업활동현금흐름", 12),
    ]
    for year in (2024, 2025):
        for order, (sj, account_id, name, amount) in enumerate(definitions):
            account_rows.append((code, year, "11011", "CFS", sj, account_id, name,
                                 amount + (10 if year == 2025 and name == "매출액" else 0),
                                 "KRW", order, "20250501", "TEST"))
    upsert_financials(conn, account_rows)


def test_ranking_and_shadow_portfolio_create_no_order_proposals(tmp_path):
    conn = connect(tmp_path / "shadow.db")
    for code, start, slope in (("AAA", 100, .2), ("BBB", 80, .1), ("069500", 90, .15)):
        seed_prices(conn, code, start, slope)
    seed_financials(conn, "AAA"); seed_financials(conn, "BBB")
    latest = (date(2025, 1, 1) + timedelta(days=159)).strftime("%Y%m%d")
    conn.executemany("INSERT INTO valuation_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)", [
        ("AAA", latest, 132, 1e12, 10, 1.2, 13.2, 110, 2.0, "TEST"),
        ("BBB", latest, 96, 8e11, 8, .8, 12, 120, 3.0, "TEST"),
    ])
    conn.commit()
    ranking = rank_universe(conn, ["AAA", "BBB"], {"AAA": "기술", "BBB": "금융"})
    assert {"per", "pbr", "value_score", "quality_score", "total_score",
            "valuation_status", "data_confidence"}.issubset(ranking.columns)
    result = run_shadow_day(conn, ["AAA", "BBB"], {"AAA": "기술", "BBB": "금융"},
                            initial_capital=10_000_000, top_n=2, min_order=1,
                            stock_cap=.5, sector_cap=.7, min_liquidity=0)
    assert not result.proposals.empty
    assert set(result.proposals["status"]) == {"SIMULATED_NO_ORDER"}
    assert conn.execute("SELECT COUNT(*) FROM shadow_book_performance WHERE portfolio_id='default'").fetchone()[0] == 1
    assert result.cash_opportunity_cost >= 0
    assert result.cash_defense >= 0
    rerun = run_shadow_day(conn, ["AAA", "BBB"], {"AAA": "기술", "BBB": "금융"},
                           initial_capital=10_000_000, top_n=2, min_order=1,
                           stock_cap=.5, sector_cap=.7, min_liquidity=0)
    assert rerun.already_processed is True
    assert rerun.proposals.empty
    assert conn.execute("SELECT COUNT(*) FROM shadow_book_proposals WHERE portfolio_id='default'").fetchone()[0] == len(result.proposals)
    second = run_shadow_day(conn, ["AAA", "BBB"], {"AAA": "기술", "BBB": "금융"},
                            initial_capital=20_000_000, top_n=2, min_order=1,
                            stock_cap=.5, sector_cap=.7, portfolio_id="shadow_24",
                            min_liquidity=0)
    assert second.already_processed is False
    assert second.portfolio_id == "shadow_24"
    assert conn.execute("SELECT COUNT(*) FROM shadow_accounts").fetchone()[0] == 2
    assert conn.execute("SELECT initial_capital FROM shadow_accounts WHERE portfolio_id='shadow_24'").fetchone()[0] == 20_000_000
    assert second.cash_opportunity_cost == 0
    assert second.cash_defense == 0
    assert abs(second.allocation_gap) < 1.0
    stored = conn.execute("SELECT strategy_version,config_hash,universe_hash FROM shadow_accounts "
                          "WHERE portfolio_id='shadow_24'").fetchone()
    assert all(stored)
    with pytest.raises(ValueError, match="저장 설정과 현재 설정이 다릅니다"):
        run_shadow_day(conn, ["AAA", "BBB"], {"AAA": "기술", "BBB": "금융"},
                       initial_capital=20_000_000, top_n=1, min_order=1,
                       stock_cap=.5, sector_cap=.7, portfolio_id="shadow_24",
                       min_liquidity=0)


def test_negative_per_is_marked_as_loss_and_not_ranked_as_cheap(tmp_path):
    conn = connect(tmp_path / "loss.db")
    for code, start, slope in (("LOSS", 100, .2), ("PROFIT", 80, .1), ("069500", 90, .15)):
        seed_prices(conn, code, start, slope)
    latest = (date(2025, 1, 1) + timedelta(days=159)).strftime("%Y%m%d")
    conn.executemany("INSERT INTO valuation_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)", [
        ("LOSS", latest, 132, 1e12, -5, 1.0, -10, 100, 2.0, "TEST"),
        ("PROFIT", latest, 96, 8e11, 10, 1.0, 10, 100, 2.0, "TEST"),
    ])
    conn.commit()
    ranking = rank_universe(conn, ["LOSS", "PROFIT"], {"LOSS": "화학", "PROFIT": "화학"})
    loss = ranking.set_index("code").loc["LOSS"]
    assert loss["earnings_status"] == "적자"
    assert "적자 PER 제외" in loss["data_warning"]
    assert loss["valuation_reference"] == "PER:전체/PBR:전체"
