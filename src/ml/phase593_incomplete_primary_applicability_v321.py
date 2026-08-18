from __future__ import annotations

import html
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd


def _plain(paths: list[Path]) -> str:
    raw = " ".join(path.read_text(encoding="utf-8") for path in paths)
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_incomplete_primary_adjustments_v321(
    *, terms_csv: str, execution_manifest_csv: str, documents_dir: str,
    trading_calendar_db: str, evidence_output_csv: str,
    review_output_csv: str, audit_output_csv: str, summary_json: str,
) -> dict:
    terms = pd.read_csv(terms_csv, dtype=str).fillna("")
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    targets = terms[terms["extraction_status"].eq(
        "MECHANIC_CONFIRMED_EFFECTIVE_TERMS_INCOMPLETE")].copy()
    descriptions = manifest.drop_duplicates("queue_event_id").set_index("queue_event_id")["source_description"]
    with sqlite3.connect(trading_calendar_db) as conn:
        first = pd.read_sql_query(
            "SELECT code, MIN(REPLACE(date, '-', '')) AS first_date FROM stock_prices GROUP BY code",
            conn, dtype=str).set_index("code")["first_date"].to_dict()
    root = Path(documents_dir)
    evidence, audits, reviews = [], [], []
    for item in targets.itertuples(index=False):
        description = str(descriptions.get(item.queue_event_id, ""))
        paths = sorted(root.glob(f"{item.controlling_mechanics_rcept_no}_*"))
        try:
            text, error = (_plain(paths), "") if paths else ("", "DOCUMENT_NOT_FOUND")
        except (OSError, UnicodeError) as exc:
            text, error = "", f"{type(exc).__name__}: {exc}"
        subsidiary = "자회사의" in description or "종속회사의" in description
        mechanic_confirmed = any(term in text for term in ("유상증자", "합병", "주식교환", "주식이전"))
        first_price = first.get(str(item.code).zfill(6), "")
        pre_listing = bool(first_price and str(item.source_reference_date) < first_price)
        if subsidiary and mechanic_confirmed:
            status = "EXPLICIT_SUBSIDIARY_ACTION_NOT_LISTED_PARENT_EVENT"
            reason = "SUBSIDIARY_ACTION_HAS_NO_LISTED_PARENT_SHARE_MECHANIC"
        elif pre_listing and mechanic_confirmed:
            status = "EXPLICIT_PRE_LISTING_PRIMARY_ACTION"
            reason = "ACTION_PRECEDES_FIRST_LISTED_PRICE_OBSERVATION"
        else:
            status = "DIRECT_LISTED_ACTION_TERMS_REPARSE_REQUIRED"
            reason = error or "DIRECT_ACTION_REQUIRES_STRUCTURED_TERMS_OR_MARKET_VALIDATION"
        not_applicable = status.startswith("EXPLICIT_")
        if not_applicable:
            evidence.append({
                "queue_event_id": item.queue_event_id,
                "verification_source": "OPENDART_CONTROLLING_DOCUMENT_PRIMARY_APPLICABILITY",
                "verification_reference": f"DART:{item.controlling_mechanics_rcept_no}",
                "resolution_note": reason,
            })
        audit = {
            "queue_event_id": item.queue_event_id, "code": str(item.code).zfill(6),
            "mechanic_family": item.mechanic_family, "controlling_rcept_no": item.controlling_mechanics_rcept_no,
            "subsidiary_disclosure": subsidiary, "mechanic_confirmed": mechanic_confirmed,
            "source_reference_date": item.source_reference_date, "first_price_date": first_price,
            "pre_listing_event": pre_listing, "applicability_status": status,
            "resolution_note": reason, "promotion_status": "NOT_APPLICABLE_EVIDENCE" if not_applicable else "NOT_PROMOTED",
            "error": error,
        }
        audits.append(audit)
        if not not_applicable:
            reviews.append(audit)
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    ep, rp, ap = Path(evidence_output_csv), Path(review_output_csv), Path(audit_output_csv)
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(reviews).to_csv(rp, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": int(len(targets)), "not_applicable_evidence_rows": int(len(evidence)),
               "direct_reparse_rows": int(len(reviews)), "evidence_output_csv": str(ep),
               "review_output_csv": str(rp), "audit_output_csv": str(ap)}
    sp = Path(summary_json); sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
