import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src.ml.total_return_v321 import build_total_return_history_v321


def _setup(tmp_path):
    db = sqlite3.connect(tmp_path / "x.db")
    db.execute("CREATE TABLE stock_prices(code TEXT,date TEXT,close REAL)")
    rows = [
        ("005930", "20200102", 100.0), ("005930", "20200103", 99.0),
        ("069500", "20200102", 200.0), ("069500", "20200103", 202.0),
    ]
    db.executemany("INSERT INTO stock_prices VALUES(?,?,?)", rows)
    db.commit()
    actions = tmp_path / "actions.csv"
    pd.DataFrame([{
        "code":"005930", "effective_date":"20200103", "action_type":"CASH_DIVIDEND",
        "adjustment_factor":1.0, "cash_amount":2.0, "known_at":"20200103", "source":"VERIFIED_TEST"
    }]).to_csv(actions, index=False)
    coverage = tmp_path / "coverage.json"
    coverage.write_text(json.dumps({
        "start":"20200102", "end":"20200103", "codes":["005930"],
        "cash_distributions_complete":True, "capital_actions_complete":True,
        "complex_actions_complete":True, "coverage_gate_status":"PASS",
        "source":"VERIFIED_TEST"
    }), encoding="utf-8")
    return db, actions, coverage


def test_total_return_builds_cash_distribution_index(tmp_path):
    db, actions, coverage = _setup(tmp_path)
    out = tmp_path / "tr.csv"
    result = build_total_return_history_v321(
        db, corporate_actions_csv=str(actions), coverage_json=str(coverage),
        output_csv=str(out), benchmark_code="069500")
    assert result["status"] == "VERIFIED_TOTAL_RETURN_INPUT"
    frame = pd.read_csv(out, dtype={"code":str})
    row = frame[(frame.code.str.zfill(6)=="005930") & (frame.date==20200103)].iloc[0]
    assert row.total_return_index == pytest.approx(101.0)


def test_total_return_rejects_incomplete_coverage(tmp_path):
    db, actions, coverage = _setup(tmp_path)
    payload = json.loads(coverage.read_text())
    payload["cash_distributions_complete"] = False
    coverage.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="cash_distributions_complete"):
        build_total_return_history_v321(
            db, corporate_actions_csv=str(actions), coverage_json=str(coverage),
            output_csv=str(tmp_path / "tr.csv"), benchmark_code="069500")


def test_total_return_rejects_coverage_without_complex_action_gate(tmp_path):
    db, actions, coverage = _setup(tmp_path)
    payload = json.loads(coverage.read_text())
    payload.pop("complex_actions_complete")
    payload.pop("coverage_gate_status")
    coverage.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage JSON"):
        build_total_return_history_v321(
            db, corporate_actions_csv=str(actions), coverage_json=str(coverage),
            output_csv=str(tmp_path / "tr.csv"), benchmark_code="069500")
