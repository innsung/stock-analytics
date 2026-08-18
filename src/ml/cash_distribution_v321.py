from __future__ import annotations

from pathlib import Path
import json
import re

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

CASH_ACTIONS = {"CASH_DIVIDEND", "ETF_DISTRIBUTION"}
PLACEHOLDER = re.compile(r"REPLACE_WITH|PLACEHOLDER|EXAMPLE|TODO|TBD", re.I)


def _clean_date(value) -> str:
    return str(value or "").replace("-", "").replace(".", "").strip()


def _number(value) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("원", "").replace("%", "")
    if text in {"", "-", "nan", "None"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _is_cash_per_share_label(label: str) -> bool:
    compact = re.sub(r"\s+", "", str(label))
    return (
        "주당현금배당금" in compact
        or "주당현금배당" in compact
        or ("주당" in compact and "배당금" in compact and "현금" in compact)
    )


def _is_common_stock(stock_kind: str) -> bool:
    text = str(stock_kind).strip().lower()
    if not text:
        return True
    return any(token in text for token in ("보통", "common", "ordinary"))


def build_stock_cash_amount_candidates_v321(
    *,
    dividend_facts_csv: str,
    verification_csv: str,
    output_csv: str,
    audit_csv: str,
    etf_codes: list[str] | None = None,
) -> dict:
    """Extract DART cash-per-share amounts as candidates only.

    The output never supplies an effective/ex-date and therefore cannot pass strict
    evidence validation by itself.
    """
    etf_codes = {str(x).zfill(6) for x in (etf_codes or ["069500"])}
    facts_path = Path(dividend_facts_csv)
    verification_path = Path(verification_csv)
    if not facts_path.exists():
        raise FileNotFoundError(f"배당 fact CSV가 없습니다: {facts_path}")
    if not verification_path.exists():
        raise FileNotFoundError(f"verification CSV가 없습니다: {verification_path}")

    facts = pd.read_csv(facts_path, dtype=str).fillna("")
    verification = pd.read_csv(verification_path, dtype=str).fillna("")
    fact_required = {"code", "business_year", "disclosed_at", "se", "stock_knd", "thstrm", "source"}
    missing = fact_required - set(facts.columns)
    if missing:
        raise ValueError("배당 fact 누락 열: " + ", ".join(sorted(missing)))
    verify_required = {"queue_event_id", "code", "event_family", "source_reference_date"}
    missing = verify_required - set(verification.columns)
    if missing:
        raise ValueError("verification CSV 누락 열: " + ", ".join(sorted(missing)))

    facts["code"] = facts["code"].astype(str).str.zfill(6)
    facts = facts[~facts["code"].isin(etf_codes)].copy()
    facts = facts[facts["se"].map(_is_cash_per_share_label)]
    facts = facts[facts["stock_knd"].map(_is_common_stock)]
    facts["candidate_cash_amount"] = facts["thstrm"].map(_number)
    facts = facts[facts["candidate_cash_amount"].notna() & facts["candidate_cash_amount"].gt(0)].copy()

    dividends = verification[
        verification["event_family"].astype(str).str.upper().eq("DIVIDEND_OR_DISTRIBUTION")
        & ~verification["code"].astype(str).str.zfill(6).isin(etf_codes)
    ].drop_duplicates("queue_event_id").copy()
    dividends["code"] = dividends["code"].astype(str).str.zfill(6)

    rows = []
    audits = []
    for _, q in dividends.iterrows():
        code = q["code"]
        ref = _clean_date(q["source_reference_date"])
        # Annual report disclosure usually happens in year+1, so candidate business
        # year is normally ref-year-1. Also include ref-year for amended/other timing.
        years = set()
        if len(ref) == 8 and ref.isdigit():
            y = int(ref[:4])
            years.update({str(y - 1), str(y)})
        matches = facts[facts["code"].eq(code)]
        if years:
            matches = matches[matches["business_year"].astype(str).isin(years)]

        # DART may publish duplicate rows from consolidated/separate contexts.
        unique_amounts = sorted(set(matches["candidate_cash_amount"].astype(float).round(12)))
        if len(unique_amounts) == 1:
            amount = unique_amounts[0]
            chosen = matches.iloc[0]
            rows.append({
                "queue_event_id": q["queue_event_id"],
                "code": code,
                "event_family": "DIVIDEND_OR_DISTRIBUTION",
                "source_reference_date": ref,
                "candidate_business_years": "|".join(sorted(years)),
                "candidate_cash_amount": amount,
                "candidate_known_at": _clean_date(chosen["disclosed_at"]),
                "candidate_source": str(chosen["source"]),
                "candidate_reference": f"OpenDART annual dividend fact:{chosen['business_year']}",
                "effective_date": "",
                "known_at": "",
                "action_type": "CASH_DIVIDEND",
                "adjustment_factor": "1",
                "cash_amount": "",
                "verification_source": "",
                "verification_reference": "",
                "promotion_status": "AMOUNT_ONLY_NEEDS_OFFICIAL_EX_DATE",
            })
            status = "UNIQUE_AMOUNT_CANDIDATE"
        elif len(unique_amounts) == 0:
            status = "NO_AMOUNT_CANDIDATE"
        else:
            status = f"AMBIGUOUS_AMOUNT_CANDIDATES:{len(unique_amounts)}"
        audits.append({
            "queue_event_id": q["queue_event_id"],
            "code": code,
            "source_reference_date": ref,
            "match_rows": int(len(matches)),
            "unique_amounts": int(len(unique_amounts)),
            "status": status,
        })

    out = pd.DataFrame(rows)
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False, encoding="utf-8-sig")
    audit = pd.DataFrame(audits)
    ap = Path(audit_csv)
    ap.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(ap, index=False, encoding="utf-8-sig")

    return {
        "queue_rows": int(len(dividends)),
        "amount_candidate_rows": int(len(out)),
        "unresolved_amount_rows": int((audit["status"] != "UNIQUE_AMOUNT_CANDIDATE").sum()) if not audit.empty else 0,
        "output_csv": str(target),
        "audit_csv": str(ap),
    }


def prepare_official_cash_event_template_v321(
    *,
    verification_csv: str,
    output_csv: str,
    etf_codes: list[str] | None = None,
) -> dict:
    """Create strict official cash-event input sheet for both stocks and ETFs."""
    etf_codes = {str(x).zfill(6) for x in (etf_codes or ["069500"])}
    v = pd.read_csv(verification_csv, dtype=str).fillna("")
    required = {"queue_event_id", "code", "event_family", "source_reference_date", "source_description"}
    missing = required - set(v.columns)
    if missing:
        raise ValueError("verification CSV 누락 열: " + ", ".join(sorted(missing)))
    v = v[v["event_family"].astype(str).str.upper().eq("DIVIDEND_OR_DISTRIBUTION")]
    v = v.drop_duplicates("queue_event_id").copy()
    v["code"] = v["code"].astype(str).str.zfill(6)
    out = pd.DataFrame({
        "queue_event_id": v["queue_event_id"],
        "code": v["code"],
        "event_family": "DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date": v["source_reference_date"],
        "security_type": v["code"].map(lambda x: "ETF" if x in etf_codes else "STOCK"),
        "effective_date": "",
        "known_at": "",
        "action_type": v["code"].map(lambda x: "ETF_DISTRIBUTION" if x in etf_codes else "CASH_DIVIDEND"),
        "adjustment_factor": "1",
        "cash_amount": "",
        "verification_source": "",
        "verification_reference": "",
        "resolution_note": "",
    })
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False, encoding="utf-8-sig")
    return {
        "rows": int(len(out)),
        "stock_rows": int((out["security_type"] == "STOCK").sum()),
        "etf_rows": int((out["security_type"] == "ETF").sum()),
        "output_csv": str(target),
    }


def validate_official_cash_events_v321(
    *,
    official_cash_events_csv: str,
    output_csv: str,
    audit_csv: str,
) -> dict:
    """Validate actual official cash-event observations into strict evidence.

    This accepts only source-backed event rows. It does not infer dates or amounts.
    Multiple rows per queue_event_id are allowed for interim/final distributions.
    """
    p = Path(official_cash_events_csv)
    if not p.exists():
        raise FileNotFoundError(f"official cash events CSV가 없습니다: {p}")
    f = pd.read_csv(p, dtype=str).fillna("")
    required = {
        "queue_event_id", "code", "event_family", "effective_date", "known_at",
        "action_type", "adjustment_factor", "cash_amount", "verification_source",
        "verification_reference",
    }
    missing = required - set(f.columns)
    if missing:
        raise ValueError("official cash events CSV 누락 열: " + ", ".join(sorted(missing)))

    f["code"] = f["code"].astype(str).str.zfill(6)
    f["effective_date"] = f["effective_date"].map(_clean_date)
    f["known_at"] = f["known_at"].map(_clean_date)
    f["action_type"] = f["action_type"].str.strip().str.upper()
    f["adjustment_factor"] = pd.to_numeric(f["adjustment_factor"], errors="coerce")
    f["cash_amount"] = pd.to_numeric(f["cash_amount"], errors="coerce")
    invalid = (
        f["queue_event_id"].str.strip().eq("")
        | ~f["event_family"].astype(str).str.upper().eq("DIVIDEND_OR_DISTRIBUTION")
        | ~f["action_type"].isin(CASH_ACTIONS)
        | f["effective_date"].str.len().ne(8)
        | f["known_at"].str.len().ne(8)
        | f["effective_date"].gt(RESEARCH_SEEN_THROUGH)
        | f["known_at"].gt(f["effective_date"])
        | f["adjustment_factor"].isna()
        | f["adjustment_factor"].sub(1.0).abs().gt(1e-12)
        | f["cash_amount"].isna() | f["cash_amount"].le(0)
        | f["verification_source"].str.strip().eq("")
        | f["verification_source"].str.contains(PLACEHOLDER)
    )
    # ETF_DISTRIBUTION is reserved for actual ETF rows; CASH_DIVIDEND for stocks.
    invalid |= f["action_type"].eq("ETF_DISTRIBUTION") & ~f["code"].eq("069500")
    audit = f[["queue_event_id", "code", "effective_date", "action_type"]].copy()
    audit["valid"] = ~invalid
    audit["error"] = invalid.map(lambda x: "INVALID_OFFICIAL_CASH_EVENT" if x else "")

    ap = Path(audit_csv)
    ap.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(ap, index=False, encoding="utf-8-sig")
    if invalid.any():
        raise ValueError(f"official cash event 엄격 검증 실패: invalid_rows={int(invalid.sum())}, audit={ap}")

    strict = f.copy()
    if "source_reference_date" not in strict.columns:
        strict["source_reference_date"] = ""
    if "resolution_note" not in strict.columns:
        strict["resolution_note"] = "STRICT_OFFICIAL_CASH_EVENT"
    cols = [
        "queue_event_id", "code", "event_family", "source_reference_date",
        "effective_date", "known_at", "action_type", "adjustment_factor",
        "cash_amount", "verification_source", "verification_reference",
        "resolution_note",
    ]
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    strict[cols].to_csv(target, index=False, encoding="utf-8-sig")
    return {
        "strict_cash_evidence_rows": int(len(strict)),
        "stock_dividend_rows": int(strict["action_type"].eq("CASH_DIVIDEND").sum()),
        "etf_distribution_rows": int(strict["action_type"].eq("ETF_DISTRIBUTION").sum()),
        "output_csv": str(target),
        "audit_csv": str(ap),
    }


def compare_cash_amount_candidates_v321(
    *,
    strict_cash_evidence_csv: str,
    amount_candidates_csv: str,
    output_csv: str,
    tolerance: float = 1e-9,
) -> dict:
    """Cross-check strict stock cash amounts against OpenDART candidates.

    Mismatch does not alter strict evidence; it creates an audit blocker for review.
    """
    strict = pd.read_csv(strict_cash_evidence_csv, dtype=str).fillna("")
    cand = pd.read_csv(amount_candidates_csv, dtype=str).fillna("")
    rows = []
    for _, r in strict.iterrows():
        qid = r["queue_event_id"]
        match = cand[cand["queue_event_id"].eq(qid)]
        official = _number(r["cash_amount"])
        candidate_values = sorted({
            x for x in match.get("candidate_cash_amount", pd.Series(dtype=str)).map(_number).tolist()
            if x is not None
        })
        if str(r["action_type"]) == "ETF_DISTRIBUTION":
            status = "ETF_NO_DART_AMOUNT_COMPARISON"
        elif not candidate_values:
            status = "NO_DART_AMOUNT_CANDIDATE"
        elif official is not None and any(abs(official - x) <= tolerance for x in candidate_values):
            status = "MATCH"
        else:
            status = "MISMATCH"
        rows.append({
            "queue_event_id": qid,
            "code": str(r["code"]).zfill(6),
            "action_type": r["action_type"],
            "official_cash_amount": official,
            "dart_candidate_amounts": "|".join(str(x) for x in candidate_values),
            "status": status,
        })
    audit = pd.DataFrame(rows)
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(target, index=False, encoding="utf-8-sig")
    return {
        "rows": int(len(audit)),
        "matches": int((audit["status"] == "MATCH").sum()) if not audit.empty else 0,
        "mismatches": int((audit["status"] == "MISMATCH").sum()) if not audit.empty else 0,
        "output_csv": str(target),
    }
