from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321


TARGETS = {
    "2d54690554bd4b486389": {
        "endpoint": "stkExtrDecsn", "rcept_no": "20210623000067",
        "date_field": "extrsc_extrdt", "event_date": "20210901",
        "listing_field": "extrsc_nstklstprd", "listing_date": "20210917",
        "ratio_field": "extr_rt", "ratio": 0.0046683,
        "counterparty_field": "extr_tgcmp_cmpnm", "action": "SHARE_EXCHANGE",
    },
    "704428b155d277ae3a09": {
        "endpoint": "cmpMgDecsn", "rcept_no": "20210621000143",
        "date_field": "mgsc_mgdt", "event_date": "20210901",
        "listing_field": "mgsc_nstklstprd", "listing_date": "",
        "ratio_field": "mg_rt", "ratio": 0.1962185,
        "counterparty_field": "mgptncmp_cmpnm", "action": "MERGER",
    },
}


def _date(value: object) -> str:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return digits[:8] if len(digits) >= 8 else ""


def _ratio(value: object) -> float | None:
    match = re.search(r"1\s*:\s*([0-9.]+)", str(value or ""))
    return float(match.group(1)) if match else None


def audit_amorepacific_restructuring_v321(
    provider, *, review_queue_csv: str, official_candidates_csv: str,
    evidence_output_csv: str, audit_output_csv: str, summary_json: str,
) -> dict:
    review = pd.read_csv(review_queue_csv, dtype=str).fillna("")
    candidates = pd.read_csv(official_candidates_csv, dtype=str).fillna("")
    evidence, audits = [], []
    breakpoints: dict[str, pd.DataFrame] = {}
    for queue_id, spec in TARGETS.items():
        queue_rows = review[review["queue_event_id"].eq(queue_id)]
        official = candidates[
            candidates["endpoint"].eq(spec["endpoint"])
            & candidates["rcept_no"].eq(spec["rcept_no"])
            & candidates["code"].astype(str).str.zfill(6).eq("090430")
        ]
        status, reason, ratio, event_date, listing_date, counterparty = (
            "UNRESOLVED", "", None, "", "", ""
        )
        event_breaks = listing_breaks = -1
        if len(queue_rows) != 1 or len(official) != 1:
            reason = "TARGET_OR_UNIQUE_CONTROLLING_OPENDART_ROW_UNAVAILABLE"
        else:
            raw = json.loads(official.iloc[0]["raw_json"])
            event_date = _date(raw.get(spec["date_field"]))
            listing_date = _date(raw.get(spec["listing_field"]))
            ratio = _ratio(raw.get(spec["ratio_field"]))
            counterparty = str(raw.get(spec["counterparty_field"], "")).strip()
            dates = [event_date] + ([listing_date] if listing_date else [])
            for center in dates:
                if center not in breakpoints:
                    breakpoints[center] = detect_adjustment_breakpoints_v321(
                        provider, code="090430", center_date=center, window_days=12)
            event_breaks = len(breakpoints.get(event_date, pd.DataFrame()))
            listing_breaks = len(breakpoints.get(listing_date, pd.DataFrame())) if listing_date else 0
            terms_ok = (
                event_date == spec["event_date"]
                and listing_date == spec["listing_date"]
                and ratio is not None and abs(ratio - spec["ratio"]) < 1e-10
                and bool(counterparty)
            )
            if spec["action"] == "MERGER":
                terms_ok = terms_ok and str(raw.get("mgnstk_cstk_cnt", "")).strip() in {"", "-", "0"}
                terms_ok = terms_ok and str(raw.get("mgnstk_ostk_cnt", "")).strip() in {"", "-", "0"}
                terms_ok = terms_ok and "자기주식" in str(raw.get("ex_sm_r", ""))
            else:
                terms_ok = terms_ok and "주식교환 대상주주" in str(raw.get("extr_rt", ""))
                terms_ok = terms_ok and "34,269" in str(raw.get("extr_rt", ""))
            if not terms_ok:
                reason = "CONTROLLING_OPENDART_RESTRUCTURING_TERMS_MISMATCH"
            elif event_breaks or listing_breaks:
                reason = "KRX_ADJUSTED_RAW_BREAKPOINT_REQUIRES_MANUAL_REVIEW"
            else:
                status = "NOT_APPLICABLE_EVIDENCE"
                reason = "TARGET_HOLDER_CONSIDERATION_DOES_NOT_CHANGE_EXISTING_ACQUIRER_HOLDER_SHARE_COUNT"
                evidence.append({
                    "queue_event_id": queue_id,
                    "verification_source": "OPENDART_CONTROLLING_RESTRUCTURING_TERMS+KRX_ADJUSTED_RAW_NO_BREAKPOINT",
                    "verification_reference": f"DART:{spec['rcept_no']}",
                    "resolution_note": reason,
                })
        audits.append({
            "queue_event_id": queue_id, "code": "090430", "action_type": spec["action"],
            "controlling_rcept_no": spec["rcept_no"], "counterparty": counterparty,
            "event_date": event_date, "new_share_listing_date": listing_date,
            "transaction_ratio": ratio, "event_window_breakpoints": event_breaks,
            "listing_window_breakpoints": listing_breaks, "verification_status": status,
            "resolution_note": reason,
        })
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": len(TARGETS), "not_applicable_evidence_rows": len(evidence),
               "unresolved_rows": len(TARGETS) - len(evidence), "evidence_output_csv": str(ep),
               "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
