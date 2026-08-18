from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


def audit_spinoff_fractional_settlement_v321(
    *, official_candidates_csv: str, valuation_audit_csv: str,
    rule_output_csv: str, scenario_output_csv: str,
    receipt_no: str = "20250822000109", scenario_quantities: tuple[int, ...] = (1, 10, 100),
) -> dict:
    official = pd.read_csv(official_candidates_csv, dtype=str).fillna("")
    selected = official[official["rcept_no"].eq(receipt_no)]
    if selected.empty:
        raise ValueError(f"official spin-off candidate unavailable: {receipt_no}")
    raw = json.loads(selected.iloc[0]["raw_json"])
    rule_text = str(raw.get("abcr_shstkcnt_rt_at_rs", ""))
    required = ("1주 미만", "재상장 초일의 종가", "현금으로 지급", "자기주식으로 취득")
    explicit_rule = all(token in rule_text for token in required)
    if not explicit_rule:
        raise ValueError("explicit fractional-share cash settlement rule unavailable")

    audit = pd.read_csv(valuation_audit_csv, dtype=str).fillna("")
    valued = audit[audit["rcept_no"].eq(receipt_no)]
    if valued.empty:
        raise ValueError(f"valuation audit unavailable: {receipt_no}")
    row = valued.iloc[0]
    child_ratio = float(row["distributed_ratio"])
    child_close = float(row["child_first_close"])
    effective_date = row["first_joint_trade_date"]

    rules = pd.DataFrame([{
        "event_id": f"SPINOFF:{receipt_no}", "effective_date": effective_date,
        "source_code": row["parent_code"], "distributed_code": row["child_code"],
        "units_per_source_share": child_ratio,
        "fractional_settlement_method": "CASH_AT_FIRST_RELISTING_CLOSE",
        "settlement_price": child_close, "fractional_shares_acquired_by": "NEW_COMPANY_TREASURY",
        "verification_source": "OPENDART_ATDVDSTDEC",
        "verification_reference": receipt_no, "rule_status": "EXPLICIT_RULE_VERIFIED",
        "canonical_status": "BLOCKED_SURVIVING_LEG_FRACTIONAL_TREATMENT_UNVERIFIED",
    }])
    scenarios = []
    for quantity in scenario_quantities:
        if int(quantity) <= 0:
            raise ValueError("scenario quantities must be positive integers")
        exact = int(quantity) * child_ratio
        whole = math.floor(exact + 1e-12)
        fractional = exact - whole
        scenarios.append({
            "event_id": f"SPINOFF:{receipt_no}", "source_shares": int(quantity),
            "exact_distributed_shares": exact, "whole_distributed_shares": whole,
            "fractional_distributed_shares": fractional,
            "fractional_cash_settlement": fractional * child_close,
            "settlement_price": child_close, "effective_date": effective_date,
        })
    rp, sp = Path(rule_output_csv), Path(scenario_output_csv)
    rp.parent.mkdir(parents=True, exist_ok=True); sp.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(rp, index=False, encoding="utf-8-sig")
    pd.DataFrame(scenarios).to_csv(sp, index=False, encoding="utf-8-sig")
    return {"verified_rules": 1, "scenario_rows": len(scenarios),
            "canonical_total_return_ready": False,
            "rule_output_csv": str(rp), "scenario_output_csv": str(sp)}
