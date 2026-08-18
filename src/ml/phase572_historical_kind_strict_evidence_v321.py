from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup


APPLY_DATE = re.compile(r"적용일\s*:?[\s]*(20\d{2})\D+(\d{1,2})\D+(\d{1,2})")
SOURCE_DATE = re.compile(r"/external/(20\d{2})/(\d{2})/(\d{2})/")


def _date(match) -> str:
    return f"{int(match.group(1)):04d}{int(match.group(2)):02d}{int(match.group(3)):02d}" if match else ""


def build_historical_kind_strict_evidence_v321(
    *, discovery_csv: str, parsed_decisions_csv: str, output_csv: str,
    audit_csv: str, timeout: int = 20, session=None,
) -> dict:
    discovery = pd.read_csv(discovery_csv, dtype=str).fillna("")
    parsed = pd.read_csv(parsed_decisions_csv, dtype=str).fillna("")
    parsed = parsed[parsed["parse_status"].eq("PARSED_DECISION_TERMS")].copy()
    parsed["code"] = parsed["code"].astype(str).str.zfill(6)
    canonical = parsed.sort_values("rcept_no").drop_duplicates(
        ["code", "common_cash_dividend_per_share", "dividend_record_date", "board_decision_date"], keep="last")
    corp_codes = canonical.groupby("corp_code")["code"].agg(lambda values: sorted(set(values))).to_dict()
    http = session or requests.Session()
    rows, audits = [], []
    for item in discovery.itertuples(index=False):
        candidate = str(item.candidate_ex_date)
        options = parsed[(parsed["queue_event_id"].eq(item.queue_event_id)) &
                         (parsed["code"].eq(item.code)) &
                         (parsed["rcept_dt"].str.replace("-", "", regex=False).le(candidate))]
        decision = next(options.sort_values("rcept_no", ascending=False).itertuples(index=False), None)
        market_date = known_at = text = error = ""
        try:
            response = http.get(item.market_source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
            response.raise_for_status()
            if (response.encoding or "").lower() == "iso-8859-1" and response.apparent_encoding:
                response.encoding = response.apparent_encoding
            text = " ".join(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True).split())
            market_date = _date(APPLY_DATE.search(text))
            known_at = _date(SOURCE_DATE.search(item.market_source_url))
        except requests.RequestException as exc:
            error = f"{type(exc).__name__}: {exc}"
        preferred = False
        amount = record = security_name = ""
        if decision:
            siblings = corp_codes.get(decision.corp_code, [item.code])
            preferred = len(siblings) > 1 and item.code != siblings[0]
            amount = (decision.preferred_cash_dividend_per_share if preferred
                      else decision.common_cash_dividend_per_share)
            record = decision.dividend_record_date.replace("-", "")
            security_name = item.company_name + ("우" if preferred else "")
        membership = bool(security_name and security_name in text)
        amount_number = pd.to_numeric(str(amount).replace(",", ""), errors="coerce")
        valid = bool(decision and membership and market_date == candidate and known_at and
                     known_at <= market_date and record >= market_date and
                     pd.notna(amount_number) and amount_number > 0)
        if not error and not decision: error = "MATCHING_PIT_DECISION_NOT_FOUND"
        elif not error and not membership: error = "SECURITY_NOT_FOUND_IN_NOTICE"
        elif not error and market_date != candidate: error = "APPLICATION_DATE_CANDIDATE_MISMATCH"
        elif not error and (not known_at or known_at > market_date): error = "INVALID_PIT_ORDER"
        elif not error and not valid: error = "INVALID_AMOUNT_OR_RECORD_DATE"
        if valid:
            rows.append({
                "queue_event_id": item.queue_event_id, "code": item.code,
                "event_family": "DIVIDEND_OR_DISTRIBUTION", "source_reference_date": record,
                "effective_date": market_date, "known_at": known_at, "action_type": "CASH_DIVIDEND",
                "adjustment_factor": 1.0, "cash_amount": float(amount_number),
                "verification_source": "OPENDART_DECISION+KRX_KIND_OFFICIAL_EXDATE_NOTICE",
                "verification_reference": f"DART:{decision.rcept_no}|KIND:{item.kind_acpt_no}/{item.kind_doc_no}|{item.market_source_url}",
                "resolution_note": "STRICT_OFFICIAL_DIVIDEND_AMOUNT_RECORD_DATE_AND_MARKET_EXDATE",
            })
        audits.append({
            "queue_event_id": item.queue_event_id, "code": item.code, "security_name": security_name,
            "amount_role": "PREFERRED" if preferred else "COMMON", "cash_amount": amount,
            "record_date": record, "known_at": known_at, "candidate_ex_date": candidate,
            "parsed_market_ex_date": market_date, "membership_verified": membership,
            "valid": valid, "error": error,
        })
    columns = ["queue_event_id", "code", "event_family", "source_reference_date", "effective_date",
               "known_at", "action_type", "adjustment_factor", "cash_amount", "verification_source",
               "verification_reference", "resolution_note"]
    output = pd.DataFrame(rows, columns=columns); audit = pd.DataFrame(audits)
    op, ap = Path(output_csv), Path(audit_csv); op.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(op, index=False, encoding="utf-8-sig"); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    return {"discovered_rows": len(discovery), "strict_rows": len(output),
            "invalid_rows": int((~audit["valid"]).sum()), "preferred_rows": int(audit["amount_role"].eq("PREFERRED").sum()),
            "output_csv": str(op), "audit_csv": str(ap)}
