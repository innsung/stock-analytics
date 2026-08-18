from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321


def _date(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return digits if len(digits) == 8 else ""


def _number(value: str) -> float | None:
    cleaned = re.sub(r"[^0-9.]", "", str(value or ""))
    return float(cleaned) if cleaned else None


def reparse_celltrion_merger_v321(
    provider, *, applicability_audit_csv: str, terms_csv: str,
    official_candidates_csv: str, evidence_output_csv: str,
    audit_output_csv: str, summary_json: str,
) -> dict:
    applicability = pd.read_csv(applicability_audit_csv, dtype=str).fillna("")
    terms = pd.read_csv(terms_csv, dtype=str).fillna("")
    official = pd.read_csv(official_candidates_csv, dtype=str).fillna("")
    targets = applicability[applicability["applicability_status"].eq("EFFECTIVE_DATE_REPARSE_REQUIRED")]
    evidence, audits = [], []
    for target in targets.itertuples(index=False):
        term = terms[terms["queue_event_id"].eq(target.queue_event_id)]
        candidates = official[
            official["code"].astype(str).str.zfill(6).eq(str(target.code).zfill(6))
            & official["endpoint"].eq("cmpMgDecsn")]
        status, reason = "UNRESOLVED", ""
        merger_date = listing_date = ratio = new_shares = receipt = ""
        merger_breakpoints = listing_breakpoints = pd.DataFrame()
        if len(term) == 1 and len(candidates) == 1:
            row = candidates.iloc[0]
            payload = json.loads(row["raw_json"])
            receipt = str(row["rcept_no"])
            merger_date = _date(payload.get("mgsc_mgdt", ""))
            listing_date = _date(payload.get("mgsc_nstklstprd", ""))
            ratio_text = str(payload.get("mg_rt", ""))
            match = re.search(r"1\s*:\s*([0-9.]+)", ratio_text)
            ratio = match.group(1) if match else ""
            share_values = [_number(payload.get("mgnstk_cstk_cnt", "")),
                            _number(payload.get("mgnstk_ostk_cnt", ""))]
            issued = [value for value in share_values if value is not None and value > 0]
            new_shares = str(int(sum(issued))) if issued else ""
            if merger_date:
                merger_breakpoints = detect_adjustment_breakpoints_v321(
                    provider, code=str(target.code).zfill(6), center_date=merger_date, window_days=15)
            if listing_date:
                listing_breakpoints = detect_adjustment_breakpoints_v321(
                    provider, code=str(target.code).zfill(6), center_date=listing_date, window_days=15)
            conditions = bool(merger_date == "20231228" and listing_date == "20240112"
                              and ratio == "0.4492620" and new_shares == "73887750")
            no_market_factor = merger_breakpoints.empty and listing_breakpoints.empty
            if conditions and no_market_factor:
                status = "ACQUIRER_SHAREHOLDER_POSITION_UNCHANGED_NO_MARKET_FACTOR"
                reason = "MERGER_CONSIDERATION_SHARES_GO_TO_TARGET_HOLDERS_WITH_NO_ACQUIRER_PRICE_ADJUSTMENT"
                controlling = term.iloc[0]["controlling_mechanics_rcept_no"]
                evidence.append({
                    "queue_event_id": target.queue_event_id,
                    "verification_source": "OPENDART_STRUCTURED_MERGER_TERMS+KRX_NO_ADJUSTED_RAW_BREAKPOINT",
                    "verification_reference": f"DART:{receipt}|DART:{controlling}",
                    "resolution_note": reason,
                })
            elif not conditions:
                reason = "STRUCTURED_MERGER_TERMS_DO_NOT_MATCH_EXPECTED_FINAL_TERMS"
            else:
                reason = "KRX_MARKET_ADJUSTMENT_BREAKPOINT_REQUIRES_FACTOR_REVIEW"
        else:
            reason = f"TERM_ROWS={len(term)}|OFFICIAL_CANDIDATES={len(candidates)}"
        audits.append({
            "queue_event_id": target.queue_event_id, "code": str(target.code).zfill(6),
            "official_rcept_no": receipt, "merger_date": merger_date,
            "new_share_listing_date": listing_date, "target_exchange_ratio": ratio,
            "merger_consideration_new_shares": new_shares,
            "merger_date_breakpoints": int(len(merger_breakpoints)),
            "listing_date_breakpoints": int(len(listing_breakpoints)),
            "validation_status": status, "resolution_note": reason,
            "promotion_status": "NOT_APPLICABLE_EVIDENCE" if status.startswith("ACQUIRER_") else "NOT_PROMOTED",
        })
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": int(len(targets)), "not_applicable_evidence_rows": int(len(evidence)),
               "unresolved_rows": int(len(targets) - len(evidence)),
               "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp = Path(summary_json); sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
