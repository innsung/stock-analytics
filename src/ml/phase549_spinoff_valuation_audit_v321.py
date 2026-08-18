from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

import pandas as pd


PriceLoader = Callable[[str, str, str, bool], pd.DataFrame]


def _number(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"spin-off ratio not found: {pattern}")
    return float(match.group(1))


def _default_loader(start: str, end: str, code: str, adjusted: bool) -> pd.DataFrame:
    from pykrx import stock
    return stock.get_market_ohlcv_by_date(start, end, code, adjusted=adjusted)


def audit_listed_spinoff_valuation_v321(
    *, official_candidates_csv: str, output_csv: str,
    receipt_no: str = "20250822000109", parent_code: str = "207940",
    child_code: str = "0126Z0", start_date: str = "20251001",
    end_date: str = "20251205", price_loader: PriceLoader | None = None,
) -> dict:
    official = pd.read_csv(official_candidates_csv, dtype=str).fillna("")
    rows = official[official["rcept_no"].eq(receipt_no)]
    if rows.empty:
        raise ValueError(f"official spin-off candidate unavailable: {receipt_no}")
    raw = json.loads(rows.iloc[0]["raw_json"])
    ratio_text = str(raw.get("dv_rt", ""))
    surviving_ratio = _number(r"분할존속회사\s*:\s*([0-9.]+)", ratio_text)
    distributed_ratio = _number(r"분할신설회사\s*:\s*([0-9.]+)", ratio_text)

    loader = price_loader or _default_loader
    raw_parent = loader(start_date, end_date, parent_code, False)
    adj_parent = loader(start_date, end_date, parent_code, True)
    raw_child = loader(start_date, end_date, child_code, False)
    close = "\uc885\uac00"
    volume = "\uac70\ub798\ub7c9"
    traded_pre = raw_parent[raw_parent[volume].astype(float).gt(0)]
    child_traded = raw_child[raw_child[volume].astype(float).gt(0)]
    first_child_date = child_traded.index.min()
    pre = traded_pre[traded_pre.index < first_child_date].iloc[-1]
    pre_date = traded_pre[traded_pre.index < first_child_date].index[-1]
    post_parent = raw_parent.loc[first_child_date]
    post_child = raw_child.loc[first_child_date]
    adjusted_pre = float(adj_parent.loc[pre_date, close])
    raw_pre = float(pre[close])
    adjustment_factor = adjusted_pre / raw_pre
    reconstructed_close_value = (
        float(post_parent[close]) * surviving_ratio
        + float(post_child[close]) * distributed_ratio
    )
    adjusted_post = float(adj_parent.loc[first_child_date, close])
    continuity_return = adjusted_post / adjusted_pre - 1.0
    audit_status = (
        "PRICE_SERIES_FACTOR_CONFIRMED_TOTAL_RETURN_REQUIRES_DISTRIBUTION_LEDGER"
        if abs(continuity_return) <= 0.05
        else "MANUAL_REVIEW_REQUIRED"
    )
    out = pd.DataFrame([{
        "rcept_no": receipt_no, "parent_code": parent_code, "child_code": child_code,
        "pre_trade_date": pd.Timestamp(pre_date).strftime("%Y%m%d"),
        "first_joint_trade_date": pd.Timestamp(first_child_date).strftime("%Y%m%d"),
        "surviving_ratio": surviving_ratio, "distributed_ratio": distributed_ratio,
        "raw_pre_close": raw_pre, "adjusted_pre_close": adjusted_pre,
        "parent_first_close": float(post_parent[close]),
        "child_first_close": float(post_child[close]),
        "parent_price_series_adjustment_factor": adjustment_factor,
        "adjusted_parent_boundary_return": continuity_return,
        "distributed_value_reconstruction": reconstructed_close_value,
        "reconstruction_return_vs_raw_pre": reconstructed_close_value / raw_pre - 1.0,
        "audit_status": audit_status, "strict_promotion_status": "NOT_PROMOTED",
        "strict_block_reason": "DISTRIBUTED_SECURITY_REQUIRES_POSITION_AND_TOTAL_RETURN_LEDGER",
    }])
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return {"audited_rows": 1, "factor": adjustment_factor,
            "audit_status": audit_status, "output_csv": str(path)}
