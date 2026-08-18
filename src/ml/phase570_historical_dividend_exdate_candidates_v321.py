from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd


def build_historical_dividend_exdate_candidates_v321(
    *, parsed_csv: str, trading_calendar_db: str, output_csv: str, summary_json: str,
) -> dict:
    parsed = pd.read_csv(parsed_csv, dtype=str).fillna("")
    required = {"queue_event_id", "code", "rcept_no", "rcept_dt",
                "common_cash_dividend_per_share", "dividend_record_date",
                "board_decision_date", "parse_status"}
    missing = required - set(parsed.columns)
    if missing:
        raise ValueError("parsed decision CSV missing columns: " + ", ".join(sorted(missing)))

    usable = parsed[parsed["parse_status"].eq("PARSED_DECISION_TERMS")].copy()
    usable["code"] = usable["code"].astype(str).str.zfill(6)
    # Corrective/repeated filings can carry identical final terms. Retain the
    # latest receipt as the canonical document without duplicating the event.
    event_key = ["code", "common_cash_dividend_per_share", "dividend_record_date", "board_decision_date"]
    usable = usable.sort_values("rcept_no").drop_duplicates(event_key, keep="last")

    db = Path(trading_calendar_db)
    if not db.exists():
        raise FileNotFoundError(str(db))
    with sqlite3.connect(db) as conn:
        dates = pd.read_sql_query("SELECT DISTINCT date FROM stock_prices ORDER BY date", conn, dtype=str)
    calendar = sorted(dates["date"].astype(str).str.replace("-", "", regex=False).unique())

    rows = []
    for item in usable.itertuples(index=False):
        record = str(item.dividend_record_date).replace("-", "")
        prior = [date for date in calendar if date < record]
        candidate = prior[-1] if prior else ""
        prior2 = prior[-2] if len(prior) >= 2 else ""
        known = str(item.rcept_dt).replace("-", "")
        pit = bool(candidate and known and known <= candidate)
        rows.append({
            "queue_event_id": item.queue_event_id,
            "code": item.code,
            "canonical_rcept_no": item.rcept_no,
            "common_cash_dividend_per_share": item.common_cash_dividend_per_share,
            "record_date": record,
            "known_at": known,
            "calendar_prior_trading_day_1": candidate,
            "calendar_prior_trading_day_2": prior2,
            "pit_order_valid_for_candidate": pit,
            "candidate_status": (
                "READY_FOR_OFFICIAL_MARKET_VERIFICATION" if pit
                else "LATE_DISCLOSURE_NOT_PIT_ELIGIBLE" if candidate
                else "TRADING_CALENDAR_UNAVAILABLE"
            ),
            "market_ex_date": "",
            "market_source": "",
            "market_reference": "",
            "strict_promotion_status": "NOT_PROMOTED_CALENDAR_CANDIDATE_ONLY",
        })
    output = pd.DataFrame(rows)
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target, index=False, encoding="utf-8-sig")
    counts = output["candidate_status"].value_counts().to_dict() if not output.empty else {}
    result = {
        "parsed_rows": int(len(usable)),
        "deduplicated_rows": int(len(parsed[parsed["parse_status"].eq("PARSED_DECISION_TERMS")]) - len(usable)),
        "ready_for_market_verification": int(counts.get("READY_FOR_OFFICIAL_MARKET_VERIFICATION", 0)),
        "late_disclosure_rows": int(counts.get("LATE_DISCLOSURE_NOT_PIT_ELIGIBLE", 0)),
        "calendar_unavailable_rows": int(counts.get("TRADING_CALENDAR_UNAVAILABLE", 0)),
        "strict_rows": 0,
        "output_csv": str(target),
        "trading_calendar_db": str(db),
    }
    summary = Path(summary_json); summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["summary_json"] = str(summary)
    return result
