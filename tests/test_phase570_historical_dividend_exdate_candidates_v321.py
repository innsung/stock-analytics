import sqlite3

import pandas as pd

from src.ml.phase570_historical_dividend_exdate_candidates_v321 import build_historical_dividend_exdate_candidates_v321


def test_builds_calendar_candidates_without_strict_promotion(tmp_path):
    rows = [
        {"queue_event_id":"q", "code":"1", "rcept_no":"1", "rcept_dt":"20240320",
         "common_cash_dividend_per_share":"500", "dividend_record_date":"2024-03-31",
         "board_decision_date":"2024-03-20", "parse_status":"PARSED_DECISION_TERMS"},
        {"queue_event_id":"q", "code":"1", "rcept_no":"2", "rcept_dt":"20240410",
         "common_cash_dividend_per_share":"500", "dividend_record_date":"2024-03-31",
         "board_decision_date":"2024-03-20", "parse_status":"PARSED_DECISION_TERMS"},
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "parsed.csv", index=False)
    db = tmp_path / "calendar.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE stock_prices (date TEXT, code TEXT)")
        conn.executemany("INSERT INTO stock_prices VALUES (?, ?)",
                         [("20240328", "005930"), ("20240329", "005930")])
    result = build_historical_dividend_exdate_candidates_v321(
        parsed_csv=str(tmp_path / "parsed.csv"), trading_calendar_db=str(db),
        output_csv=str(tmp_path / "out.csv"), summary_json=str(tmp_path / "summary.json"))
    out = pd.read_csv(tmp_path / "out.csv", dtype=str).fillna("")
    assert result["deduplicated_rows"] == 1
    assert out.loc[0, "canonical_rcept_no"] == "2"
    assert out.loc[0, "calendar_prior_trading_day_1"] == "20240329"
    assert out.loc[0, "candidate_status"] == "LATE_DISCLOSURE_NOT_PIT_ELIGIBLE"
    assert out.loc[0, "strict_promotion_status"] == "NOT_PROMOTED_CALENDAR_CANDIDATE_ONLY"
