from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time
from typing import Callable

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

SOURCE_DIVIDEND = "OPENDART_ALOT_MATTER"
SOURCE_DISCLOSURE = "OPENDART_DISCLOSURE_LIST"
ACTION_KEYWORDS = (
    "주식분할", "액면분할", "주식병합", "액면병합",
    "회사분할", "분할합병", "합병", "주식교환", "주식이전",
    "무상증자", "유상증자", "감자", "상장폐지", "거래정지",
)


def _clean_date(value: str | int | None) -> str:
    return str(value or "").replace("-", "").replace(".", "").strip()


def _safe_year_end(year: int) -> str:
    return min(f"{int(year)}1231", RESEARCH_SEEN_THROUGH)


def _call_with_retry(fn: Callable, *, max_retries: int, backoff_seconds: float):
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn(), attempt, ""
        except Exception as exc:  # provider/network errors are audited, not hidden
            last = exc
            if attempt < max_retries:
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))
    return None, max_retries, f"{type(last).__name__}: {last}"


def _normalize_dividend_rows(code: str, corp_code: str, year: int, report_code: str,
                             disclosed_at: str, rows: list[dict]) -> list[dict]:
    out = []
    for raw in rows:
        # Preserve the official OpenDART row as JSON so schema additions do not
        # silently discard evidence. Common fields are also flattened for review.
        out.append({
            "code": code,
            "corp_code": corp_code,
            "business_year": int(year),
            "report_code": report_code,
            "disclosed_at": _clean_date(disclosed_at),
            "se": str(raw.get("se", "")),
            "stock_knd": str(raw.get("stock_knd", "")),
            "thstrm": str(raw.get("thstrm", "")),
            "frmtrm": str(raw.get("frmtrm", "")),
            "lwfr": str(raw.get("lwfr", "")),
            "source": SOURCE_DIVIDEND,
            "raw_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
            "promotion_status": "DISCLOSURE_FACT_ONLY_NOT_EFFECTIVE_CASH_EVENT",
        })
    return out


def _normalize_action_disclosures(code: str, corp_code: str, rows: list[dict]) -> list[dict]:
    out = []
    for raw in rows:
        name = str(raw.get("report_nm", ""))
        if not any(k in name for k in ACTION_KEYWORDS):
            continue
        receipt = _clean_date(raw.get("rcept_dt"))
        if not receipt or receipt > RESEARCH_SEEN_THROUGH:
            continue
        out.append({
            "code": code,
            "corp_code": corp_code,
            "rcept_dt": receipt,
            "report_nm": name,
            "rcept_no": str(raw.get("rcept_no", "")),
            "flr_nm": str(raw.get("flr_nm", "")),
            "source": SOURCE_DISCLOSURE,
            "raw_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
            "promotion_status": "DISCLOSURE_ONLY_EFFECTIVE_DATE_NOT_VERIFIED",
        })
    return out


def acquire_payout_action_facts_v321(
    dart_client,
    *,
    codes: list[str],
    start_year: int,
    end_year: int,
    output_dir: str,
    max_retries: int = 3,
    retry_backoff_seconds: float = 1.0,
    sleep_seconds: float = 0.05,
) -> dict:
    """Acquire raw OpenDART dividend/action facts without fabricating effective dates.

    The output is deliberately *not* a canonical corporate_actions.csv. It is an
    evidence layer that must be reconciled with ex/effective dates before Total
    Return can be marked VERIFIED.
    """
    if int(start_year) > int(end_year):
        raise ValueError("start_year는 end_year보다 클 수 없습니다.")
    if int(start_year) < 1999:
        raise ValueError("start_year가 비정상적으로 이릅니다.")
    if int(end_year) > int(RESEARCH_SEEN_THROUGH[:4]):
        end_year = int(RESEARCH_SEEN_THROUGH[:4])

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    corp_map = dart_client.corp_code_map()
    dividends: list[dict] = []
    disclosures: list[dict] = []
    audits: list[dict] = []

    total = len(codes) * (end_year - start_year + 1)
    done = 0
    for code_index, code in enumerate(codes, 1):
        code = str(code).zfill(6)
        corp_code = corp_map.get(code, "")
        if not corp_code:
            audits.append({
                "code": code, "business_year": "", "status": "NO_DART_CORP_CODE",
                "dividend_rows": 0, "action_rows": 0, "attempts": 0, "error": "",
            })
            continue

        for year in range(int(start_year), int(end_year) + 1):
            done += 1
            print(f"[{code_index}/{len(codes)}] {code} [{year}] ({done}/{total}) OpenDART 조회...")

            div_rows, div_attempts, div_error = _call_with_retry(
                lambda c=corp_code, y=year: dart_client.dividend_matters(c, y, "11011"),
                max_retries=max_retries, backoff_seconds=retry_backoff_seconds,
            )
            disclosure_date = ""
            if div_rows is not None:
                try:
                    disclosure_date = dart_client.disclosure_date(corp_code, year, "11011") or ""
                except Exception:
                    disclosure_date = ""
                dividends.extend(_normalize_dividend_rows(
                    code, corp_code, year, "11011", disclosure_date, div_rows
                ))

            begin = f"{year}0101"
            end = _safe_year_end(year)
            act_rows, act_attempts, act_error = _call_with_retry(
                lambda c=corp_code, b=begin, e=end: dart_client.disclosure_list(c, b, e),
                max_retries=max_retries, backoff_seconds=retry_backoff_seconds,
            )
            norm_actions = _normalize_action_disclosures(code, corp_code, act_rows or [])
            disclosures.extend(norm_actions)

            status = "OK"
            errors = [e for e in (div_error, act_error) if e]
            if div_rows is None and act_rows is None:
                status = "FAILED"
            elif errors:
                status = "PARTIAL"
            audits.append({
                "code": code, "business_year": year, "status": status,
                "dividend_rows": len(div_rows or []), "action_rows": len(norm_actions),
                "attempts": max(div_attempts, act_attempts),
                "error": " | ".join(errors),
            })
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    dividend_frame = pd.DataFrame(dividends, columns=[
        "code", "corp_code", "business_year", "report_code", "disclosed_at",
        "se", "stock_knd", "thstrm", "frmtrm", "lwfr", "source", "raw_json",
        "promotion_status",
    ])
    action_frame = pd.DataFrame(disclosures, columns=[
        "code", "corp_code", "rcept_dt", "report_nm", "rcept_no", "flr_nm",
        "source", "raw_json", "promotion_status",
    ])
    audit_frame = pd.DataFrame(audits)

    dividend_path = target / "dividend_disclosure_facts.csv"
    disclosure_path = target / "corporate_action_disclosures.csv"
    audit_path = target / "payout_action_acquisition_audit.csv"
    dividend_frame.to_csv(dividend_path, index=False, encoding="utf-8-sig")
    action_frame.to_csv(disclosure_path, index=False, encoding="utf-8-sig")
    audit_frame.to_csv(audit_path, index=False, encoding="utf-8-sig")

    failed = int((audit_frame["status"] == "FAILED").sum()) if not audit_frame.empty else 0
    partial = int((audit_frame["status"] == "PARTIAL").sum()) if not audit_frame.empty else 0
    manifest = {
        "phase": "V3.2.1 Phase 5.3",
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "codes_requested": len(codes),
        "start_year": int(start_year),
        "end_year": int(end_year),
        "dividend_fact_rows": int(len(dividend_frame)),
        "corporate_action_disclosure_rows": int(len(action_frame)),
        "failed_year_requests": failed,
        "partial_year_requests": partial,
        "status": "RAW_DISCLOSURE_FACTS_ACQUIRED" if failed == 0 else "RAW_DISCLOSURE_FACTS_PARTIAL",
        "canonical_corporate_actions_verified": False,
        "total_return_ready": False,
        "reason_not_total_return_ready": (
            "OpenDART dividend/report facts and decision disclosures do not by themselves "
            "prove ex-date/payment-date/effective-date coverage. Reconciliation is required."
        ),
        "outputs": {
            "dividend_disclosure_facts": str(dividend_path),
            "corporate_action_disclosures": str(disclosure_path),
            "audit": str(audit_path),
        },
    }
    manifest_path = target / "payout_action_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest | {"manifest_path": str(manifest_path)}


def build_event_reconciliation_template_v321(*, dividend_facts_csv: str,
                                             action_disclosures_csv: str,
                                             output_csv: str) -> dict:
    """Build a human/provider reconciliation queue; never auto-promotes raw facts."""
    dividends = pd.read_csv(dividend_facts_csv, dtype=str).fillna("")
    actions = pd.read_csv(action_disclosures_csv, dtype=str).fillna("")
    rows = []
    if not dividends.empty:
        grouped = dividends.groupby(["code", "business_year"], dropna=False)
        for (code, year), g in grouped:
            disclosed = g["disclosed_at"].astype(str)
            disclosed = disclosed[disclosed.str.len() == 8]
            known = disclosed.min() if not disclosed.empty else ""
            rows.append({
                "code": str(code).zfill(6),
                "event_family": "DIVIDEND_OR_DISTRIBUTION",
                "source_reference_date": str(known),
                "source_description": f"OpenDART alotMatter {year}",
                "candidate_cash_amount": "",
                "candidate_adjustment_factor": "1",
                "candidate_effective_date": "",
                "candidate_known_at": str(known),
                "action_type": "",
                "verification_source": "",
                "verification_status": "NEEDS_EX_DATE_PAYMENT_DATE_VERIFICATION",
            })
    if not actions.empty:
        for r in actions.itertuples(index=False):
            rows.append({
                "code": str(r.code).zfill(6),
                "event_family": "CORPORATE_ACTION",
                "source_reference_date": str(r.rcept_dt),
                "source_description": str(r.report_nm),
                "candidate_cash_amount": "0",
                "candidate_adjustment_factor": "",
                "candidate_effective_date": "",
                "candidate_known_at": str(r.rcept_dt),
                "action_type": "",
                "verification_source": "",
                "verification_status": "NEEDS_EFFECTIVE_DATE_AND_FACTOR_VERIFICATION",
            })
    frame = pd.DataFrame(rows)
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False, encoding="utf-8-sig")
    return {"rows": int(len(frame)), "output_csv": str(out)}
