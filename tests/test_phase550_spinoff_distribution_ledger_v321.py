import pandas as pd
import pytest

from src.ml.phase550_spinoff_distribution_ledger_v321 import build_spinoff_distribution_ledger_v321


def _audit(path, surviving=0.65, distributed=0.35):
    pd.DataFrame([{
        "rcept_no": "r1", "parent_code": "207940", "child_code": "0126Z0",
        "first_joint_trade_date": "20251124", "surviving_ratio": surviving,
        "distributed_ratio": distributed, "parent_first_close": 1500,
        "child_first_close": 400,
        "audit_status": "PRICE_SERIES_FACTOR_CONFIRMED_TOTAL_RETURN_REQUIRES_DISTRIBUTION_LEDGER",
    }]).to_csv(path, index=False)


def test_builds_balanced_two_leg_spinoff_ledger(tmp_path):
    source, output = tmp_path / "audit.csv", tmp_path / "ledger.csv"
    _audit(source)
    result = build_spinoff_distribution_ledger_v321(
        valuation_audit_csv=str(source), output_csv=str(output))
    ledger = pd.read_csv(output, dtype=str)
    assert result["ledger_rows"] == 2
    assert result["canonical_total_return_ready"] is False
    assert set(ledger["entry_type"]) == {"SURVIVING_SECURITY", "DISTRIBUTED_SECURITY"}
    assert pd.to_numeric(ledger["units_per_source_share"]).sum() == pytest.approx(1.0)
    assert pd.to_numeric(ledger["valuation_amount"]).sum() == pytest.approx(1115.0)


def test_rejects_unbalanced_ratios(tmp_path):
    source = tmp_path / "audit.csv"
    _audit(source, surviving=0.7, distributed=0.4)
    with pytest.raises(ValueError, match="invalid spin-off allocation ratios"):
        build_spinoff_distribution_ledger_v321(
            valuation_audit_csv=str(source), output_csv=str(tmp_path / "ledger.csv"))
