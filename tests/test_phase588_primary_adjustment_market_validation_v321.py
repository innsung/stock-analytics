import sqlite3

import pandas as pd

from src.ml.phase588_primary_adjustment_market_validation_v321 import validate_primary_adjustment_market_dates_v321


class Provider:
    def ohlcv(self, start, end, code, adjusted):
        values = [100, 50, 50] if not adjusted else [100, 100, 100]
        return pd.DataFrame({"date": pd.to_datetime(["2022-04-04", "2022-04-05", "2022-04-06"]), "close": values})


def test_promotes_only_unique_split_market_breakpoint(tmp_path):
    pd.DataFrame([{"queue_event_id": "q1", "code": "042700", "source_reference_date": "20220223",
                  "mechanic_family": "SHARE_SPLIT_OR_CONSOLIDATION", "official_effective_date_candidate": "20220405",
                  "controlling_mechanics_rcept_no": "receipt",
                  "extraction_status": "TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION"}]).to_csv(tmp_path / "terms.csv", index=False)
    pd.DataFrame([{"queue_event_id": "q1", "source_description": "주식분할결정"}]).to_csv(tmp_path / "manifest.csv", index=False)
    with sqlite3.connect(tmp_path / "prices.db") as conn:
        pd.DataFrame({"date": ["2022-04-04", "2022-04-05", "2022-04-06"]}).to_sql("stock_prices", conn, index=False)
    result = validate_primary_adjustment_market_dates_v321(
        Provider(), terms_csv=str(tmp_path / "terms.csv"), execution_manifest_csv=str(tmp_path / "manifest.csv"),
        trading_calendar_db=str(tmp_path / "prices.db"), evidence_output_csv=str(tmp_path / "e.csv"),
        audit_output_csv=str(tmp_path / "a.csv"), summary_json=str(tmp_path / "s.json"))
    assert result["strict_market_evidence_rows"] == 1
    row = pd.read_csv(tmp_path / "e.csv", dtype=str).iloc[0]
    assert row["queue_event_id"] == "q1"
    assert row["action_type"] == "SPLIT"
    assert float(row["adjustment_factor"]) == 2.0
