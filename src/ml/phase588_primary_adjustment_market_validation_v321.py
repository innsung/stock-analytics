from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH
from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321


def validate_primary_adjustment_market_dates_v321(
    provider, *, terms_csv: str, execution_manifest_csv: str,
    trading_calendar_db: str, evidence_output_csv: str,
    audit_output_csv: str, summary_json: str,
    max_match_distance_days: int = 10,
) -> dict:
    terms = pd.read_csv(terms_csv, dtype=str).fillna("")
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    candidates = terms[terms["extraction_status"].eq("TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION")].copy()
    descriptions = manifest.drop_duplicates("queue_event_id").set_index("queue_event_id")["source_description"]
    db = Path(trading_calendar_db)
    if not db.exists():
        raise FileNotFoundError(str(db))
    with sqlite3.connect(db) as conn:
        calendar = pd.read_sql_query("SELECT DISTINCT date FROM stock_prices ORDER BY date", conn, dtype=str)
    trading_dates = sorted(set(calendar["date"].str.replace("-", "", regex=False)))

    evidence, audits = [], []
    for item in candidates.itertuples(index=False):
        known_at = str(item.source_reference_date)
        candidate_date = str(item.official_effective_date_candidate)
        description = descriptions.get(item.queue_event_id, "")
        if item.mechanic_family == "SHARE_SPLIT_OR_CONSOLIDATION":
            action = "REVERSE_SPLIT" if "병합" in description else "SPLIT" if "분할" in description else ""
        else:
            action = ""
        calendar_before = [date for date in trading_dates if date <= candidate_date]
        prior_trading_date = calendar_before[-1] if calendar_before else ""
        pit_valid = bool(len(known_at) == 8 and len(candidate_date) == 8 and
                         known_at <= candidate_date <= RESEARCH_SEEN_THROUGH)
        breakpoints = pd.DataFrame()
        status, reason = "UNRESOLVED", ""
        if not pit_valid:
            reason = "INVALID_PIT_OR_RESEARCH_CUTOFF_ORDER"
        elif action not in {"SPLIT", "REVERSE_SPLIT"}:
            reason = "ACTION_REQUIRES_COMPLEX_MARKET_SEMANTICS"
        else:
            breakpoints = detect_adjustment_breakpoints_v321(
                provider, code=str(item.code).zfill(6), center_date=candidate_date)
            nearby = breakpoints[breakpoints["distance_days"] <= int(max_match_distance_days)]
            if len(nearby) == 1:
                point = nearby.iloc[0]
                factor = float(point["ratio_change"])
                effective = str(point["date"])
                if math.isfinite(factor) and factor > 0 and known_at <= effective <= RESEARCH_SEEN_THROUGH:
                    evidence.append({
                        "queue_event_id": item.queue_event_id, "code": str(item.code).zfill(6),
                        "event_family": "CORPORATE_ACTION", "source_reference_date": candidate_date,
                        "effective_date": effective, "known_at": known_at, "action_type": action,
                        "adjustment_factor": factor, "cash_amount": 0.0,
                        "verification_source": "OPENDART_CONTROLLING_DOCUMENT+KRX_ADJUSTED_RAW_PRICE_RATIO",
                        "verification_reference": f"DART:{item.controlling_mechanics_rcept_no}|ratio:{float(point['previous_ratio']):.12g}->{float(point['ratio']):.12g}",
                        "resolution_note": "UNIQUE_KRX_MARKET_BREAKPOINT_NEAR_OFFICIAL_SPLIT_DATE",
                    })
                    status = "VERIFIED_MARKET_FACTOR"
                else:
                    reason = "INVALID_BREAKPOINT_FACTOR_OR_PIT_ORDER"
            elif len(nearby) == 0:
                reason = "NO_KRX_ADJUSTMENT_BREAKPOINT"
            else:
                reason = f"AMBIGUOUS_KRX_BREAKPOINTS:{len(nearby)}"
        audits.append({
            "queue_event_id": item.queue_event_id, "code": str(item.code).zfill(6),
            "mechanic_family": item.mechanic_family, "market_action_type": action,
            "known_at": known_at, "official_effective_date_candidate": candidate_date,
            "prior_or_same_trading_date": prior_trading_date, "pit_order_valid": pit_valid,
            "breakpoints_found": int(len(breakpoints)), "validation_status": status, "reason": reason,
        })
    columns = ["queue_event_id", "code", "event_family", "source_reference_date", "effective_date",
               "known_at", "action_type", "adjustment_factor", "cash_amount", "verification_source",
               "verification_reference", "resolution_note"]
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {
        "extracted_candidate_rows": int(len(candidates)),
        "pit_valid_rows": int(sum(bool(row["pit_order_valid"]) for row in audits)),
        "safe_market_factor_candidates": int(sum(row["market_action_type"] in {"SPLIT", "REVERSE_SPLIT"} and bool(row["pit_order_valid"]) for row in audits)),
        "strict_market_evidence_rows": int(len(evidence)),
        "complex_or_invalid_rows": int(len(candidates) - len(evidence)),
        "evidence_output_csv": str(ep), "audit_output_csv": str(ap),
    }
    sp = Path(summary_json); sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
