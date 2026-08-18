from __future__ import annotations

from pathlib import Path
import json
import re

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH


DATE_RE = re.compile(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})")
AMOUNT_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*원")


def _clean_date(v: str) -> str:
    s = re.sub(r"[^0-9]", "", str(v or ""))
    if len(s) != 8:
        return ""
    try:
        pd.to_datetime(s, format="%Y%m%d")
    except Exception:
        return ""
    return s


def build_explicit_stock_exdate_strict_evidence_v321(
    *,
    stock_dividend_date_resolution_csv: str,
    output_csv: str,
    audit_csv: str,
) -> dict:
    """Promote only rows whose official date role is explicitly EX_DATE.

    RECORD_DATE candidates are never converted here. This function is intentionally
    narrow: it requires unique amount + explicit official ex-date + PIT ordering.
    """
    p = Path(stock_dividend_date_resolution_csv)
    if not p.exists():
        raise FileNotFoundError(f"stock dividend date resolution CSV가 없습니다: {p}")
    f = pd.read_csv(p, dtype=str).fillna("")
    required = {
        "queue_event_id", "code", "candidate_cash_amount",
        "official_date_match_status", "official_date_role",
        "official_date_candidate", "official_date_known_at",
        "official_date_source", "official_date_reference",
    }
    missing = required - set(f.columns)
    if missing:
        raise ValueError("stock dividend date resolution 누락 열: " + ", ".join(sorted(missing)))

    rows = []
    audits = []
    for _, r in f.iterrows():
        role = str(r["official_date_role"]).upper().strip()
        date = _clean_date(r["official_date_candidate"])
        known = _clean_date(r["official_date_known_at"])
        try:
            amount = float(str(r["candidate_cash_amount"]).replace(",", ""))
        except Exception:
            amount = float("nan")

        status = "UNRESOLVED"
        reason = ""
        if r["official_date_match_status"] != "UNIQUE_OFFICIAL_DATE_CANDIDATE":
            reason = "OFFICIAL_DATE_NOT_UNIQUE"
        elif role != "EX_DATE":
            reason = "DATE_ROLE_NOT_EX_DATE"
        elif len(date) != 8 or date > RESEARCH_SEEN_THROUGH:
            reason = "INVALID_EX_DATE"
        elif len(known) != 8 or known > date:
            reason = "INVALID_PIT_KNOWN_AT"
        elif pd.isna(amount) or amount <= 0:
            reason = "INVALID_CASH_AMOUNT"
        elif not str(r["official_date_source"]).strip():
            reason = "MISSING_OFFICIAL_SOURCE"
        else:
            rows.append({
                "queue_event_id": r["queue_event_id"],
                "code": str(r["code"]).zfill(6),
                "event_family": "DIVIDEND_OR_DISTRIBUTION",
                "source_reference_date": r.get("source_reference_date", ""),
                "effective_date": date,
                "known_at": known,
                "action_type": "CASH_DIVIDEND",
                "adjustment_factor": 1.0,
                "cash_amount": amount,
                "verification_source": r["official_date_source"],
                "verification_reference": r["official_date_reference"],
                "resolution_note": "STRICT_EXPLICIT_OFFICIAL_EX_DATE",
            })
            status = "STRICT_EXDATE_EVIDENCE"
        audits.append({
            "queue_event_id": r["queue_event_id"],
            "code": str(r["code"]).zfill(6),
            "official_date_role": role,
            "official_date_candidate": date,
            "status": status,
            "reason": reason,
        })

    out = pd.DataFrame(rows)
    audit = pd.DataFrame(audits)
    op = Path(output_csv)
    ap = Path(audit_csv)
    op.parent.mkdir(parents=True, exist_ok=True)
    ap.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(op, index=False, encoding="utf-8-sig")
    audit.to_csv(ap, index=False, encoding="utf-8-sig")
    counts = audit["status"].value_counts().to_dict() if not audit.empty else {}
    return {
        "input_rows": int(len(f)),
        "strict_rows": int(len(out)),
        "status_counts": {str(k): int(v) for k, v in counts.items()},
        "output_csv": str(op),
        "audit_csv": str(ap),
    }


def build_record_date_calendar_candidates_v321(
    *,
    stock_dividend_date_resolution_csv: str,
    benchmark_prices_csv: str,
    output_csv: str,
) -> dict:
    """Create non-strict market-calendar candidates for RECORD_DATE rows.

    The benchmark trading calendar is used only to show nearby prior/next trading
    days. No settlement assumption is converted into strict evidence.
    """
    p = Path(stock_dividend_date_resolution_csv)
    if not p.exists():
        raise FileNotFoundError(str(p))
    bp = Path(benchmark_prices_csv)
    if not bp.exists():
        raise FileNotFoundError(str(bp))
    f = pd.read_csv(p, dtype=str).fillna("")
    b = pd.read_csv(bp, dtype=str).fillna("")
    date_col = "date" if "date" in b.columns else ("Date" if "Date" in b.columns else None)
    if date_col is None:
        raise ValueError("benchmark prices CSV에 date 열이 필요합니다.")
    trading = sorted({_clean_date(x) for x in b[date_col] if _clean_date(x)})
    rows = []
    for _, r in f.iterrows():
        if str(r["official_date_role"]).upper() != "RECORD_DATE":
            continue
        record = _clean_date(r["official_date_candidate"])
        if not record:
            continue
        prior = [d for d in trading if d < record]
        nexts = [d for d in trading if d >= record]
        rows.append({
            "queue_event_id": r["queue_event_id"],
            "code": str(r["code"]).zfill(6),
            "record_date": record,
            "prior_trading_day_1": prior[-1] if len(prior) >= 1 else "",
            "prior_trading_day_2": prior[-2] if len(prior) >= 2 else "",
            "next_or_same_trading_day": nexts[0] if nexts else "",
            "promotion_status": "CALENDAR_CONTEXT_ONLY_NOT_EXDATE_EVIDENCE",
        })
    out = pd.DataFrame(rows)
    op = Path(output_csv)
    op.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(op, index=False, encoding="utf-8-sig")
    return {"rows": int(len(out)), "output_csv": str(op)}


def parse_kodex_distribution_tables_v321(
    *,
    bodies_dir: str,
    output_csv: str,
    audit_csv: str,
) -> dict:
    """Parse saved official KODEX response bodies for table-like date/amount rows.

    This scans the already saved Phase 5.13 bodies and emits candidate rows only
    when a local table/row contains both a concrete date and a positive won amount.
    """
    root = Path(bodies_dir)
    if not root.exists():
        raise FileNotFoundError(f"KODEX response body directory가 없습니다: {root}")
    rows = []
    audits = []
    for p in sorted(root.glob("*")):
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        compact = re.sub(r"\s+", " ", text)
        hits = 0
        for m in DATE_RE.finditer(compact):
            ctx = compact[max(0, m.start()-250):min(len(compact), m.end()+350)]
            if not any(k in ctx for k in ("분배금", "배당", "distribution", "dividend")):
                continue
            amounts = AMOUNT_RE.findall(ctx)
            if not amounts:
                continue
            date = f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"
            if date > RESEARCH_SEEN_THROUGH:
                continue
            unique_amounts = []
            for a in amounts:
                try:
                    v = float(a.replace(",", ""))
                    if v > 0 and v not in unique_amounts:
                        unique_amounts.append(v)
                except Exception:
                    pass
            for amount in unique_amounts:
                rows.append({
                    "body_file": str(p),
                    "candidate_date": date,
                    "cash_amount": amount,
                    "context": ctx[:700],
                    "verification_source": "SAMSUNG_KODEX_SAVED_OFFICIAL_RESPONSE",
                    "promotion_status": "DATE_AMOUNT_PAIR_CANDIDATE_ONLY",
                })
                hits += 1
        audits.append({
            "body_file": str(p),
            "bytes": p.stat().st_size,
            "date_amount_pairs": hits,
        })
    out = pd.DataFrame(rows).drop_duplicates(
        subset=["body_file", "candidate_date", "cash_amount"]
    ) if rows else pd.DataFrame(columns=[
        "body_file","candidate_date","cash_amount","context",
        "verification_source","promotion_status"
    ])
    audit = pd.DataFrame(audits)
    op = Path(output_csv)
    ap = Path(audit_csv)
    op.parent.mkdir(parents=True, exist_ok=True)
    ap.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(op, index=False, encoding="utf-8-sig")
    audit.to_csv(ap, index=False, encoding="utf-8-sig")
    result = {
        "body_files": int(len(audit)),
        "candidate_pairs": int(len(out)),
        "files_with_pairs": int((audit["date_amount_pairs"] > 0).sum()) if not audit.empty else 0,
        "output_csv": str(op),
        "audit_csv": str(ap),
    }
    mp = op.with_name(op.stem + "_manifest.json")
    mp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["manifest"] = str(mp)
    return result

def export_benchmark_calendar_from_db_v321(
    conn,
    *,
    code: str,
    output_csv: str,
    include_post_cutoff: bool = False,
) -> dict:
    """Export the persisted benchmark trading dates without mutating the DB."""
    code = str(code).zfill(6)
    frame = pd.read_sql_query(
        "SELECT date, close FROM stock_prices WHERE code=? ORDER BY date",
        conn,
        params=(code,),
    )
    if frame.empty:
        raise ValueError(f"benchmark {code} 가격 데이터가 없습니다.")
    frame["date"] = frame["date"].astype(str)
    if not include_post_cutoff:
        frame = frame[frame["date"] <= RESEARCH_SEEN_THROUGH]
    frame = frame.drop_duplicates("date")
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False, encoding="utf-8-sig")
    return {
        "code": code,
        "rows": int(len(frame)),
        "first_date": str(frame["date"].min()),
        "last_date": str(frame["date"].max()),
        "output_csv": str(out),
    }

