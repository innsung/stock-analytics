import sqlite3
from pathlib import Path

import pytest

from src.ml.persistent_data_v321 import (
    inspect_persistent_data_v321, assert_persistent_data_v321, backup_database_v321,
)


def _db(path: Path):
    c = sqlite3.connect(path)
    c.executescript('''
    CREATE TABLE stock_prices(code TEXT,date TEXT,close REAL);
    CREATE TABLE valuation_snapshots(code TEXT,snapshot_date TEXT);
    CREATE TABLE ml_features(code TEXT,feature_date TEXT);
    CREATE TABLE ml_labels(code TEXT,feature_date TEXT);
    ''')
    return c


def test_health_and_backup_preserve_counts(tmp_path):
    db = tmp_path / "stock.db"
    c = _db(db)
    c.executemany("INSERT INTO stock_prices VALUES(?,?,?)", [
        ("069500", "20200102", 100.0), ("005930", "20200102", 50.0)])
    c.execute("INSERT INTO valuation_snapshots VALUES('005930','20200131')")
    c.execute("INSERT INTO ml_features VALUES('005930','20200203')")
    c.execute("INSERT INTO ml_labels VALUES('005930','20200203')")
    c.commit()
    health = assert_persistent_data_v321(c, db)
    assert health.healthy_for_v321
    result = backup_database_v321(c, db, str(tmp_path / "backup"), "pre_update")
    assert result["verified"]
    assert Path(result["backup_path"]).exists()
    with sqlite3.connect(result["backup_path"]) as b:
        assert b.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0] == 2


def test_guard_refuses_empty_derived_data(tmp_path):
    db = tmp_path / "stock.db"
    c = _db(db)
    c.executemany("INSERT INTO stock_prices VALUES(?,?,?)", [
        ("069500", "20200102", 100.0), ("005930", "20200102", 50.0)])
    c.execute("INSERT INTO valuation_snapshots VALUES('005930','20200131')")
    c.commit()
    with pytest.raises(RuntimeError, match="persistent data guard failed"):
        assert_persistent_data_v321(c, db)
