from __future__ import annotations

from pathlib import Path

import pandas as pd


LEDGER_COLUMNS = [
    "event_id", "effective_date", "known_at", "source_code", "received_code",
    "units_per_source_share", "entry_type", "valuation_close", "valuation_amount",
    "verification_source", "verification_reference", "ledger_status",
]


def build_spinoff_distribution_ledger_v321(
    *, valuation_audit_csv: str, output_csv: str,
) -> dict:
    audit = pd.read_csv(valuation_audit_csv, dtype=str).fillna("")
    if audit.empty:
        raise ValueError("listed spin-off valuation audit is empty")
    rows = []
    for r in audit.itertuples(index=False):
        surviving = float(r.surviving_ratio)
        distributed = float(r.distributed_ratio)
        if surviving <= 0 or distributed <= 0 or abs(surviving + distributed - 1.0) > 1e-6:
            raise ValueError(f"invalid spin-off allocation ratios: {r.rcept_no}")
        if r.audit_status != "PRICE_SERIES_FACTOR_CONFIRMED_TOTAL_RETURN_REQUIRES_DISTRIBUTION_LEDGER":
            raise ValueError(f"valuation audit is not ledger-ready: {r.rcept_no}")
        event_id = f"SPINOFF:{r.rcept_no}"
        common = {
            "event_id": event_id,
            "effective_date": r.first_joint_trade_date,
            "known_at": r.first_joint_trade_date,
            "source_code": r.parent_code,
            "verification_source": "DART_KRX_RECONSTRUCTION",
            "verification_reference": r.rcept_no,
            "ledger_status": "VALUED_NOT_CANONICAL_TOTAL_RETURN",
        }
        for code, units, close, entry_type in (
            (r.parent_code, surviving, float(r.parent_first_close), "SURVIVING_SECURITY"),
            (r.child_code, distributed, float(r.child_first_close), "DISTRIBUTED_SECURITY"),
        ):
            rows.append(common | {
                "received_code": code,
                "units_per_source_share": units,
                "entry_type": entry_type,
                "valuation_close": close,
                "valuation_amount": units * close,
            })
    ledger = pd.DataFrame(rows, columns=LEDGER_COLUMNS)
    path = Path(output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(path, index=False, encoding="utf-8-sig")
    return {
        "events": int(ledger["event_id"].nunique()),
        "ledger_rows": len(ledger),
        "distributed_security_rows": int(ledger["entry_type"].eq("DISTRIBUTED_SECURITY").sum()),
        "canonical_total_return_ready": False,
        "output_csv": str(path),
    }
