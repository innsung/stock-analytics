import json
from pathlib import Path

import pandas as pd
import pytest

from database.database import connect
from src.ml.data_integrity_v321 import (
    build_data_foundation_v321,
    import_valuation_snapshots,
    read_corporate_actions_csv_v321,
    read_total_return_csv_v321,
    read_universe_history_csv_v321,
    read_valuation_snapshot_csv,
)


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_phase3_rejects_placeholder_and_post_cutoff(tmp_path):
    placeholder = _write(tmp_path / "v.csv", "code,snapshot_date,price,market_cap,per,pbr,eps,bps,dividend_yield,known_at,source\n005930,20260709,1,1,,,,,,20260709,REPLACE_WITH_VERIFIABLE_SOURCE\n")
    _, ok, _ = read_valuation_snapshot_csv(placeholder)
    assert not ok
    future = _write(tmp_path / "tr.csv", "code,date,total_return_index,known_at,source\n005930,20260710,1000,20260710,KRX_VERIFIED\n")
    _, ok, _ = read_total_return_csv_v321(future)
    assert not ok


def test_phase3_builds_canonical_foundation(tmp_path):
    v = _write(tmp_path / "v.csv", "code,snapshot_date,price,market_cap,per,pbr,eps,bps,dividend_yield,known_at,source\n005930,20260709,60000,350000000000000,12,1.2,5000,50000,2,20260709,KRX_ARCHIVE\n")
    tr = _write(tmp_path / "tr.csv", "code,date,total_return_index,known_at,source\n005930,20260709,1000,20260709,KRX_TR\n069500,20260709,1000,20260709,ETF_TR\n")
    ca = _write(tmp_path / "ca.csv", "code,effective_date,action_type,adjustment_factor,cash_amount,known_at,source\n005930,20260630,CASH_DIVIDEND,1,361,20260601,DART_KRX\n")
    uh = _write(tmp_path / "uh.csv", "code,effective_from,effective_to,selection_known_at,listing_date,delisting_date,industry,liquidity_eligible,source\n005930,20260101,20260709,20251220,19750611,,전기전자,true,KRX_INDEX\n")
    out = tmp_path / "foundation"
    result = build_data_foundation_v321(
        valuation_csv=v, total_return_csv=tr, corporate_actions_csv=ca,
        universe_history_csv=uh, output_dir=str(out))
    assert result["all_four_verified"] is True
    assert (out / "foundation_audit.csv").exists()
    manifest = json.loads((out / "foundation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["research_seen_through"] == "20260709"
    assert len(manifest["outputs"]) == 4


def test_phase3_known_at_is_persisted_without_breaking_legacy_table(tmp_path):
    db = connect(tmp_path / "x.db")
    v = _write(tmp_path / "v.csv", "code,snapshot_date,price,market_cap,per,pbr,eps,bps,dividend_yield,known_at,source\n005930,20260709,60000,350000000000000,12,1.2,5000,50000,2,20260708,KRX_ARCHIVE\n")
    import_valuation_snapshots(db, v)
    row = db.execute("SELECT known_at FROM valuation_snapshot_meta WHERE code='005930' AND snapshot_date='20260709'").fetchone()
    assert row == ("20260708",)
    # Legacy INSERT without column names remains compatible (10-column table).
    db.execute("INSERT INTO valuation_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)",
               ("000660", "20260709", 100000, 1e14, 8, 1, 10000, 100000, 1, "TEST"))
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM valuation_snapshots").fetchone()[0] == 2


def test_phase3_other_readers_enforce_pit(tmp_path):
    ca = _write(tmp_path / "ca.csv", "code,effective_date,action_type,adjustment_factor,cash_amount,known_at,source\n005930,20260101,SPLIT,2,0,20260102,KRX\n")
    _, ok, _ = read_corporate_actions_csv_v321(ca)
    assert not ok
    uh = _write(tmp_path / "uh.csv", "code,effective_from,effective_to,selection_known_at,listing_date,delisting_date,industry,liquidity_eligible,source\n005930,20260101,,20260102,19750611,,전기전자,true,KRX\n")
    _, ok, _ = read_universe_history_csv_v321(uh)
    assert not ok
