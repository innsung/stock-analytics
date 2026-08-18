from __future__ import annotations

from pathlib import Path

import pandas as pd


def _number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def reconcile_kind_dividend_candidates_v321(
    *,
    market_queue_csv: str,
    crosscheck_csv: str,
    parsed_csv: str,
    audit_csv: str,
    official_facts_csv: str,
) -> dict:
    for value in (market_queue_csv, crosscheck_csv, parsed_csv):
        if not Path(value).exists():
            raise FileNotFoundError(value)

    queue = pd.read_csv(market_queue_csv, dtype=str).fillna("")
    crosscheck = pd.read_csv(crosscheck_csv, dtype=str).fillna("")
    parsed = pd.read_csv(parsed_csv, dtype=str).fillna("")
    targets = queue[queue["priority"].eq("P1_RECORD_DATE_READY_FOR_MARKET_VERIFICATION")].copy()

    mapped = targets.merge(
        crosscheck[["queue_event_id", "kind_acpt_no", "kind_doc_no"]],
        on="queue_event_id",
        how="left",
    ).merge(parsed, on=["kind_acpt_no", "kind_doc_no"], how="left", suffixes=("_queue", "_kind"))

    candidate_amount = _number(mapped["candidate_cash_amount"])
    common_amount = _number(mapped["common_cash_amount"])
    preferred_amount = _number(mapped["preferred_cash_amount"])
    mapped["kind_amount_match"] = candidate_amount.eq(common_amount) | candidate_amount.eq(preferred_amount)
    mapped["kind_record_date_match"] = (
        mapped["record_date_queue"].str.replace(r"[^0-9]", "", regex=True)
        .eq(mapped["record_date_kind"].str.replace(r"[^0-9]", "", regex=True))
    )
    mapped["kind_candidate_status"] = "KIND_DOCUMENT_UNAVAILABLE"
    parsed_ok = mapped["parse_status"].eq("SUCCESS")
    mapped.loc[parsed_ok & mapped["kind_record_date_match"] & ~mapped["kind_amount_match"], "kind_candidate_status"] = "REJECTED_AMOUNT_MISMATCH"
    mapped.loc[parsed_ok & ~mapped["kind_record_date_match"], "kind_candidate_status"] = "REJECTED_RECORD_DATE_MISMATCH"
    mapped.loc[parsed_ok & mapped["kind_record_date_match"] & mapped["kind_amount_match"], "kind_candidate_status"] = "KIND_FACT_MATCHED"
    mapped["promotion_status"] = "NOT_PROMOTED_AS_MARKET_EXDATE_EVIDENCE"

    audit_columns = [
        "queue_event_id", "code", "candidate_cash_amount", "kind_acpt_no", "kind_doc_no",
        "common_cash_amount", "preferred_cash_amount", "record_date_queue", "record_date_kind",
        "kind_amount_match", "kind_record_date_match", "kind_candidate_status", "promotion_status",
    ]
    audit = mapped[audit_columns].copy()

    facts = mapped[parsed_ok].drop_duplicates(["kind_acpt_no", "kind_doc_no"]).copy()
    facts = pd.DataFrame({
        "code": facts["code"].astype(str).str.zfill(6),
        "kind_acpt_no": facts["kind_acpt_no"],
        "kind_doc_no": facts["kind_doc_no"],
        "common_cash_amount": facts["common_cash_amount"],
        "preferred_cash_amount": facts["preferred_cash_amount"],
        "total_cash_amount": facts["total_cash_amount"],
        "record_date": facts["record_date_kind"],
        "payment_date": facts["payment_date"],
        "board_date": facts["board_date"],
        "verification_status": "KIND_DOCUMENT_VERIFIED",
        "promotion_status": "OFFICIAL_DIVIDEND_FACT_NOT_EXDATE_EVIDENCE",
        "document_path": facts["document_path"],
    })

    audit_path = Path(audit_csv)
    facts_path = Path(official_facts_csv)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    facts.to_csv(facts_path, index=False, encoding="utf-8-sig")
    return {
        "candidate_rows": int(len(audit)),
        "candidate_status_counts": audit["kind_candidate_status"].value_counts().to_dict(),
        "official_fact_rows": int(len(facts)),
        "audit_csv": str(audit_path),
        "official_facts_csv": str(facts_path),
    }
