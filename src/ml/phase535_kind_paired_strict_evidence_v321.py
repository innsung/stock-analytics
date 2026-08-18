from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.ml.phase528_kind_market_exdate_v321 import APPLY_DATE_RE, SOURCE_DATE_RE, _date_from_match


def build_paired_kind_market_observations_v321(
    *, pairing_csv: str, parsed_decisions_csv: str, output_csv: str,
    audit_csv: str, timeout: int = 20,
) -> dict:
    pairing = pd.read_csv(pairing_csv, dtype=str).fillna("")
    parsed = pd.read_csv(parsed_decisions_csv, dtype=str).fillna("")
    required_p = {
        "code", "company_name", "market_notice_url", "market_kind_acpt_no",
        "decision_kind_acpt_no", "decision_kind_doc_no", "status",
    }
    required_d = {
        "kind_acpt_no", "kind_doc_no", "common_cash_amount", "record_date", "parse_status",
    }
    if required_p - set(pairing.columns):
        raise ValueError("pairing missing columns: " + ", ".join(sorted(required_p - set(pairing.columns))))
    if required_d - set(parsed.columns):
        raise ValueError("parsed decisions missing columns: " + ", ".join(sorted(required_d - set(parsed.columns))))
    merged = pairing.merge(
        parsed, left_on=["decision_kind_acpt_no", "decision_kind_doc_no"],
        right_on=["kind_acpt_no", "kind_doc_no"], how="left",
    )
    observations, audits = [], []
    for _, row in merged.iterrows():
        market_ex_date, known_at, error, http_status = "", "", "", ""
        valid = row["status"] == "ACQUIRED" and row["parse_status"] == "SUCCESS"
        try:
            response = requests.get(row["market_notice_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
            http_status = str(response.status_code); response.raise_for_status()
            if (response.encoding or "").lower() == "iso-8859-1" and response.apparent_encoding:
                response.encoding = response.apparent_encoding
            text = " ".join(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True).split())
            market_ex_date = _date_from_match(APPLY_DATE_RE.search(text))
            source_match = SOURCE_DATE_RE.search(row["market_notice_url"])
            known_at = (f"{source_match.group('year')}{source_match.group('month')}{source_match.group('day')}"
                        if source_match else "")
            membership_reference = str(row.get("market_membership_reference", "")).strip()
            if row["company_name"] not in text and not membership_reference:
                valid, error = False, "COMPANY_NOT_FOUND_IN_MARKET_NOTICE"
            elif not market_ex_date:
                valid, error = False, "APPLICATION_DATE_NOT_FOUND"
        except requests.RequestException as exc:
            valid, error = False, f"{type(exc).__name__}: {exc}"
        amount = pd.to_numeric(str(row["common_cash_amount"]).replace(",", ""), errors="coerce")
        valid = bool(valid and known_at and market_ex_date and known_at <= market_ex_date
                     and len(str(row["record_date"])) == 8 and pd.notna(amount) and amount > 0)
        if valid:
            observations.append({
                "queue_event_id": "KIND-MARKET-" + row["market_kind_acpt_no"],
                "code": str(row["code"]).zfill(6), "candidate_cash_amount": amount,
                "record_date": row["record_date"], "known_at": known_at,
                "market_ex_date": market_ex_date, "market_source": "KRX_KIND_OFFICIAL_EXDATE_NOTICE",
                "market_reference": membership_reference or row["market_notice_url"],
                "market_source_url": row["market_notice_url"],
                "market_note": "Official KIND decision amount/record date paired with official market ex-date notice"
                               + (" and official membership attachment" if membership_reference else ""),
                "verification_status": "OFFICIAL_PAIRED_MARKET_EXDATE_ACQUIRED",
            })
        audits.append({
            "code": str(row["code"]).zfill(6), "market_kind_acpt_no": row["market_kind_acpt_no"],
            "decision_kind_acpt_no": row["decision_kind_acpt_no"], "record_date": row["record_date"],
            "cash_amount": row["common_cash_amount"], "known_at": known_at,
            "market_ex_date": market_ex_date, "valid": valid, "http_status": http_status, "error": error,
        })
    output, audit = pd.DataFrame(observations), pd.DataFrame(audits)
    op, ap = Path(output_csv), Path(audit_csv); op.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(op, index=False, encoding="utf-8-sig"); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    return {"paired_rows": len(merged), "valid_observations": len(output),
            "invalid_rows": int((~audit["valid"]).sum()), "output_csv": str(op), "audit_csv": str(ap)}
