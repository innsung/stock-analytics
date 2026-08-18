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


def audit_historical_merger_spinoff_applicability_v321(
    *, terms_csv: str, execution_manifest_csv: str, documents_dir: str,
    trading_calendar_db: str, evidence_output_csv: str,
    audit_output_csv: str, summary_json: str,
) -> dict:
    terms = pd.read_csv(terms_csv, dtype=str).fillna("")
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    targets = terms[
        terms["mechanic_family"].isin(["MERGER", "SPINOFF_OR_SPLIT_MERGER"])
        & terms["extraction_status"].eq("TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION")
    ].copy()
    descriptions = manifest.drop_duplicates("queue_event_id").set_index("queue_event_id")["source_description"]
    db = Path(trading_calendar_db)
    if not db.exists():
        raise FileNotFoundError(str(db))
    with sqlite3.connect(db) as conn:
        first = pd.read_sql_query(
            "SELECT code, MIN(REPLACE(date, '-', '')) AS first_date FROM stock_prices GROUP BY code",
            conn, dtype=str).set_index("code")["first_date"].to_dict()
    root = Path(documents_dir)
    evidence, audits = [], []
    for item in targets.itertuples(index=False):
        description = str(descriptions.get(item.queue_event_id, ""))
        paths = sorted(root.glob(f"{item.controlling_mechanics_rcept_no}_*"))
        try:
            text, error = (_plain(paths), "") if paths else ("", "DOCUMENT_NOT_FOUND")
        except (OSError, UnicodeError) as exc:
            text, error = "", f"{type(exc).__name__}: {exc}"
        subsidiary = "자회사의" in description or "종속회사의" in description
        no_new_share_merger = "무증자합병" in text and ("신주를발행하지" in text or "합병신주" in text)
        physical_spinoff = "물적분할" in text and "인적분할" not in text
        candidate_date = str(item.official_effective_date_candidate)
        pit_order = bool(len(candidate_date) == 8 and str(item.source_reference_date) <= candidate_date)
        first_price = first.get(str(item.code).zfill(6), "")
        pre_listing = bool(pit_order and first_price and candidate_date < first_price)
        if subsidiary:
            status = "EXPLICIT_SUBSIDIARY_RESTRUCTURING"
            reason = "SUBSIDIARY_RESTRUCTURING_HAS_NO_LISTED_PARENT_SHARE_MECHANIC"
        elif pre_listing:
            status = "EXPLICIT_PRE_LISTING_RESTRUCTURING"
            reason = "EVENT_PRECEDES_FIRST_LISTED_PRICE_OBSERVATION"
        elif no_new_share_merger:
            status = "EXPLICIT_NO_NEW_SHARE_MERGER"
            reason = "NO_CAPITAL_INCREASE_MERGER_HAS_NO_LISTED_SHARE_ADJUSTMENT"
        elif item.mechanic_family == "SPINOFF_OR_SPLIT_MERGER" and physical_spinoff:
            status = "EXPLICIT_PHYSICAL_SPINOFF_NO_SHAREHOLDER_DISTRIBUTION"
            reason = "PHYSICAL_SPINOFF_ISSUES_NO_DISTRIBUTED_SECURITY_TO_PARENT_SHAREHOLDERS"
        elif not pit_order:
            status = "EFFECTIVE_DATE_REPARSE_REQUIRED"
            reason = "EXTRACTED_EFFECTIVE_DATE_PRECEDES_DISCLOSURE"
        else:
            status = "MATERIAL_RESTRUCTURING_VALUATION_REQUIRED"
            reason = ""
        not_applicable = status.startswith("EXPLICIT_")
        if not_applicable:
            evidence.append({
                "queue_event_id": item.queue_event_id,
                "verification_source": "OPENDART_CONTROLLING_DOCUMENT_RESTRUCTURING_APPLICABILITY",
                "verification_reference": f"DART:{item.controlling_mechanics_rcept_no}",
                "resolution_note": reason,
            })
        audits.append({
            "queue_event_id": item.queue_event_id, "code": str(item.code).zfill(6),
            "mechanic_family": item.mechanic_family, "controlling_rcept_no": item.controlling_mechanics_rcept_no,
            "subsidiary_disclosure": subsidiary, "no_new_share_merger": no_new_share_merger,
            "physical_spinoff": physical_spinoff, "effective_date_candidate": candidate_date,
            "pit_order_valid": pit_order, "first_price_date": first_price, "pre_listing_event": pre_listing,
            "applicability_status": status, "resolution_note": reason,
            "promotion_status": "NOT_APPLICABLE_EVIDENCE" if not_applicable else "NOT_PROMOTED",
            "error": error,
        })
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    counts = pd.Series([row["applicability_status"] for row in audits]).value_counts().to_dict()
    summary = {
        "target_rows": int(len(targets)), "not_applicable_evidence_rows": int(len(evidence)),
        "material_or_reparse_rows": int(len(targets) - len(evidence)),
        "status_counts": {str(k): int(v) for k, v in counts.items()},
        "evidence_output_csv": str(ep), "audit_output_csv": str(ap),
    }
    sp = Path(summary_json); sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
