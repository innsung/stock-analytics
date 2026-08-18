from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd


PriceLoader = Callable[[str, str, str, bool], pd.DataFrame]


def _default_loader(start: str, end: str, code: str, adjusted: bool) -> pd.DataFrame:
    from pykrx import stock
    return stock.get_market_ohlcv_by_date(start, end, code, adjusted=adjusted)


def verify_samsung_sdi_rights_v321(
    *, evidence_output_csv: str, audit_output_csv: str,
    queue_event_id: str = "de483cac24c6cf1fa712", code: str = "006400",
    known_at: str = "20250409", verification_reference: str = "20250409001154",
    allotment_ratio: float = 0.1414150945, first_issue_price: float = 146200.0,
    start_date: str = "20250401", end_date: str = "20250418",
    price_loader: PriceLoader | None = None,
) -> dict:
    loader = price_loader or _default_loader
    raw = loader(start_date, end_date, code, False)
    adjusted = loader(start_date, end_date, code, True)
    close = "종가"
    common = raw.index.intersection(adjusted.index)
    raw_close = pd.to_numeric(raw.loc[common, close], errors="coerce")
    adj_close = pd.to_numeric(adjusted.loc[common, close], errors="coerce")
    ratio = adj_close / raw_close
    changed = ratio[(ratio - 1.0).abs() > 1e-8]
    unchanged = ratio[(ratio - 1.0).abs() <= 1e-8]
    if changed.empty or unchanged.empty:
        raise ValueError("KRX adjusted/raw rights boundary unavailable")
    pre_date = changed.index.max()
    post_dates = unchanged[unchanged.index > pre_date]
    if post_dates.empty:
        raise ValueError("KRX post-rights boundary unavailable")
    effective_date = post_dates.index.min()
    raw_pre = float(raw_close.loc[pre_date]); adjusted_pre = float(adj_close.loc[pre_date])
    factor = raw_pre / adjusted_pre
    theoretical_terp = (raw_pre + allotment_ratio * first_issue_price) / (1.0 + allotment_ratio)
    observed_terp = adjusted_pre
    theoretical_gap = observed_terp / theoretical_terp - 1.0
    boundary_confirmed = abs(theoretical_gap) <= 0.01 and str(effective_date.strftime("%Y%m%d")) == "20250410"
    if not boundary_confirmed:
        raise ValueError(f"rights boundary failed theoretical check: gap={theoretical_gap}")
    evidence = pd.DataFrame([{
        "queue_event_id": queue_event_id, "code": code,
        "event_family": "CORPORATE_ACTION", "source_reference_date": known_at,
        "effective_date": effective_date.strftime("%Y%m%d"), "known_at": known_at,
        "action_type": "RIGHTS", "adjustment_factor": factor, "cash_amount": 0.0,
        "verification_source": "KRX_ADJUSTED_RAW_BOUNDARY_AND_OPENDART_RIGHTS_TERMS",
        "verification_reference": verification_reference,
        "resolution_note": "RIGHTS_FACTOR_CONFIRMED_BY_KRX_BOUNDARY",
    }])
    audit = pd.DataFrame([{
        "code": code, "pre_boundary_date": pre_date.strftime("%Y%m%d"),
        "effective_date": effective_date.strftime("%Y%m%d"), "raw_pre_close": raw_pre,
        "adjusted_pre_close": adjusted_pre, "adjustment_factor": factor,
        "allotment_ratio": allotment_ratio, "first_issue_price": first_issue_price,
        "theoretical_terp": theoretical_terp, "observed_adjusted_pre_close": observed_terp,
        "theoretical_gap": theoretical_gap, "verification_status": "STRICT_EVIDENCE_READY",
    }])
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    ep.parent.mkdir(parents=True, exist_ok=True); ap.parent.mkdir(parents=True, exist_ok=True)
    evidence.to_csv(ep, index=False, encoding="utf-8-sig"); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    return {"evidence_rows": 1, "effective_date": effective_date.strftime("%Y%m%d"),
            "adjustment_factor": factor, "theoretical_gap": theoretical_gap,
            "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
