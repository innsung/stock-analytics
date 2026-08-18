import sqlite3

import pandas as pd
import pytest

from database.database import connect
from src.ml.data_integrity_v321 import (
    import_valuation_snapshots,
    read_valuation_snapshot_csv,
    selection_persistence_audit,
)


def test_valuation_snapshot_import_is_strict_and_upserts(tmp_path):
    db = tmp_path / "test.db"
    conn = connect(db)
    csv = tmp_path / "valuation.csv"
    pd.DataFrame([{
        "code": "5930", "snapshot_date": "20260709", "price": "60000",
        "market_cap": "350000000000000", "per": "12.1", "pbr": "1.2",
        "eps": "5000", "bps": "50000", "dividend_yield": "2.1",
        "known_at": "20260709", "source": "TEST_SOURCE",
    }]).to_csv(csv, index=False)
    summary = import_valuation_snapshots(conn, str(csv))
    assert summary["rows"] == 1
    row = conn.execute("SELECT code,snapshot_date,market_cap,source FROM valuation_snapshots").fetchone()
    assert row[0] == "005930"
    assert row[1] == "20260709"
    assert row[2] > 0
    assert row[3] == "TEST_SOURCE"
    conn.close()


def test_valuation_snapshot_rejects_post_cutoff(tmp_path):
    csv = tmp_path / "valuation.csv"
    pd.DataFrame([{
        "code": "005930", "snapshot_date": "20260710", "price": "60000",
        "market_cap": "350000000000000", "per": "12.1", "pbr": "1.2",
        "eps": "5000", "bps": "50000", "dividend_yield": "2.1",
        "known_at": "20260710", "source": "TEST_SOURCE",
    }]).to_csv(csv, index=False)
    frame, verified, status = read_valuation_snapshot_csv(str(csv))
    assert not verified
    assert status == "INVALID_VALUATION_SNAPSHOT_INPUT"
    assert not frame["row_valid"].iloc[0]


def test_selection_persistence_separates_supported_repeat_selection():
    dates = ["20240101", "20240201", "20240301", "20240401", "20240501"]
    holdings = pd.DataFrame([{
        "scope": "validation_v31_champion", "feature_date": d, "top_fraction": .20,
        "code": "005930", "name": "Samsung", "industry": "IT", "score": .9,
        "score_percentile": 1.0, "forward_return": 5.0,
    } for d in dates])
    periods = pd.DataFrame([{
        "scope": "validation_v31_champion", "feature_date": d, "top_fraction": .20,
        "universe_equal_weight_return": 1.0, "etf_return": 2.0,
    } for d in dates])
    audit = selection_persistence_audit(holdings, periods)
    row = audit.iloc[0]
    assert row["held_rate"] == pytest.approx(1.0)
    assert row["max_consecutive_selections"] == 5
    assert bool(row["persistent_flag"])
    assert bool(row["persistent_but_supported"])
