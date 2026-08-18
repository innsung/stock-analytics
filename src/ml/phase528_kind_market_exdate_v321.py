from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup


APPLY_DATE_RE = re.compile(r"적용일\s*[:：]?\s*(20\d{2})\D+(\d{1,2})\D+(\d{1,2})")
SOURCE_DATE_RE = re.compile(r"/external/(?P<year>20\d{2})/(?P<month>\d{2})/(?P<day>\d{2})/")


def _date_from_match(match: re.Match[str] | None) -> str:
    if not match:
        return ""
    return f"{int(match.group(1)):04d}{int(match.group(2)):02d}{int(match.group(3)):02d}"


def acquire_kind_market_exdates_v321(
    *,
    manifest_csv: str,
    official_facts_csv: str,
    output_csv: str,
    audit_csv: str,
    timeout: int = 20,
) -> dict:
    manifest_path = Path(manifest_csv)
    facts_path = Path(official_facts_csv)
    if not manifest_path.exists():
        raise FileNotFoundError(str(manifest_path))
    if not facts_path.exists():
        raise FileNotFoundError(str(facts_path))
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    facts = pd.read_csv(facts_path, dtype=str).fillna("")
    required = {"code", "company_name", "source_url", "expected_record_date"}
    missing = required - set(manifest.columns)
    if missing:
        raise ValueError("manifest missing columns: " + ", ".join(sorted(missing)))

    fact_by_code = facts.drop_duplicates("code").set_index("code").to_dict("index")
    observations = []
    audits = []
    for _, row in manifest.iterrows():
        code = str(row["code"]).zfill(6)
        source_url = row["source_url"].strip()
        status, error, market_ex_date, known_at = "FAILED", "", "", ""
        http_status, final_url = "", ""
        try:
            response = requests.get(
                source_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=timeout,
                allow_redirects=True,
            )
            http_status = str(response.status_code)
            final_url = response.url or source_url
            response.raise_for_status()
            if (response.encoding or "").lower() == "iso-8859-1" and response.apparent_encoding:
                response.encoding = response.apparent_encoding
            text = " ".join(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True).split())
            market_ex_date = _date_from_match(APPLY_DATE_RE.search(text))
            source_match = SOURCE_DATE_RE.search(final_url)
            known_at = (
                f"{source_match.group('year')}{source_match.group('month')}{source_match.group('day')}"
                if source_match else ""
            )
            if row["company_name"] not in text:
                error = "COMPANY_NOT_FOUND_IN_OFFICIAL_NOTICE"
            elif not market_ex_date:
                error = "APPLICATION_DATE_NOT_FOUND"
            else:
                status = "SUCCESS"
        except requests.RequestException as exc:
            error = f"{type(exc).__name__}: {exc}"

        fact = fact_by_code.get(code, {})
        if status == "SUCCESS":
            observations.append({
                "queue_event_id": "KIND-" + str(fact.get("kind_acpt_no", code)),
                "code": code,
                "candidate_cash_amount": fact.get("common_cash_amount", ""),
                "record_date": fact.get("record_date", row["expected_record_date"]),
                "known_at": known_at,
                "market_ex_date": market_ex_date,
                "market_source": "KRX_KIND_OFFICIAL_EXDATE_NOTICE",
                "market_reference": final_url,
                "market_source_url": final_url,
                "market_note": "Official KRX/KIND dividend ex-date base-price notice",
                "verification_status": "OFFICIAL_MARKET_EXDATE_ACQUIRED",
            })
        audits.append({
            "code": code,
            "company_name": row["company_name"],
            "expected_record_date": row["expected_record_date"],
            "market_ex_date": market_ex_date,
            "known_at": known_at,
            "status": status,
            "http_status": http_status,
            "final_url": final_url,
            "error": error,
        })

    output = pd.DataFrame(observations)
    audit = pd.DataFrame(audits)
    output_path = Path(output_csv)
    audit_path = Path(audit_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    return {
        "manifest_rows": int(len(manifest)),
        "acquired_rows": int(len(output)),
        "status_counts": audit["status"].value_counts().to_dict(),
        "output_csv": str(output_path),
        "audit_csv": str(audit_path),
    }
