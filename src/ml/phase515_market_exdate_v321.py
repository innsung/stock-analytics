from __future__ import annotations

from pathlib import Path
import json
import re

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

PLACEHOLDER = re.compile(r"REPLACE_WITH|PLACEHOLDER|EXAMPLE|TODO|TBD", re.I)


def _clean_date(v: str) -> str:
    s = re.sub(r"[^0-9]", "", str(v or ""))
    if len(s) != 8:
        return ""
    try:
        pd.to_datetime(s, format="%Y%m%d")
    except Exception:
        return ""
    return s


def build_market_exdate_verification_queue_v321(
    *,
    stock_dividend_date_resolution_csv: str,
    record_date_calendar_candidates_csv: str,
    output_csv: str,
) -> dict:
    """Create a prioritized verification queue for unresolved stock cash dividends.

    Calendar-derived prior trading days are context only. No candidate is promoted
    to strict evidence without an explicit official market/source observation.
    """
    rp = Path(stock_dividend_date_resolution_csv)
    cp = Path(record_date_calendar_candidates_csv)
    if not rp.exists():
        raise FileNotFoundError(str(rp))
    if not cp.exists():
        raise FileNotFoundError(str(cp))

    resolution = pd.read_csv(rp, dtype=str).fillna("")
    calendar = pd.read_csv(cp, dtype=str).fillna("")
    required_r = {
        "queue_event_id","code","candidate_cash_amount",
        "official_date_match_status","official_date_role","official_date_candidate",
        "official_date_known_at","official_date_source","official_date_reference",
    }
    missing = required_r - set(resolution.columns)
    if missing:
        raise ValueError("resolution CSV 누락 열: " + ", ".join(sorted(missing)))
    required_c = {
        "queue_event_id","record_date","prior_trading_day_1","prior_trading_day_2",
        "next_or_same_trading_day",
    }
    missing = required_c - set(calendar.columns)
    if missing:
        raise ValueError("calendar candidate CSV 누락 열: " + ", ".join(sorted(missing)))

    merged = resolution.merge(
        calendar[[
            "queue_event_id","record_date","prior_trading_day_1",
            "prior_trading_day_2","next_or_same_trading_day",
        ]],
        on="queue_event_id", how="left",
    )
    rows=[]
    for _,r in merged.iterrows():
        role=str(r["official_date_role"]).upper()
        priority="P3_NO_OFFICIAL_DATE"
        if r["official_date_match_status"]=="UNIQUE_OFFICIAL_DATE_CANDIDATE" and role=="RECORD_DATE":
            priority="P1_RECORD_DATE_READY_FOR_MARKET_VERIFICATION"
        elif r["official_date_match_status"]=="UNIQUE_OFFICIAL_DATE_CANDIDATE":
            priority="P2_UNIQUE_NON_RECORD_DATE"
        elif str(r["official_date_match_status"]).startswith("AMBIGUOUS"):
            priority="P2_AMBIGUOUS_OFFICIAL_DATE"

        rows.append({
            "queue_event_id":r["queue_event_id"],
            "code":str(r["code"]).zfill(6),
            "candidate_cash_amount":r["candidate_cash_amount"],
            "official_date_match_status":r["official_date_match_status"],
            "official_date_role":role,
            "record_date":r.get("record_date","") or (
                r["official_date_candidate"] if role=="RECORD_DATE" else ""
            ),
            "calendar_prior_trading_day_1":r.get("prior_trading_day_1",""),
            "calendar_prior_trading_day_2":r.get("prior_trading_day_2",""),
            "calendar_next_or_same_trading_day":r.get("next_or_same_trading_day",""),
            "known_at":r["official_date_known_at"],
            "official_document_source":r["official_date_source"],
            "official_document_reference":r["official_date_reference"],
            "priority":priority,
            "market_ex_date":"",
            "market_source":"",
            "market_reference":"",
            "market_source_url":"",
            "market_note":"",
            "verification_status":"UNRESOLVED",
        })
    out=pd.DataFrame(rows).sort_values(["priority","code","queue_event_id"])
    op=Path(output_csv); op.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(op,index=False,encoding="utf-8-sig")
    counts=out["priority"].value_counts().to_dict() if not out.empty else {}
    return {
        "rows":int(len(out)),
        "priority_counts":{str(k):int(v) for k,v in counts.items()},
        "output_csv":str(op),
    }


def validate_official_market_exdates_v321(
    *,
    verification_csv: str,
    strict_evidence_csv: str,
    audit_csv: str,
) -> dict:
    """Validate manually/acquired official market ex-date observations.

    Calendar suggestions are ignored for validation. Strict evidence requires a
    populated official `market_ex_date` and non-placeholder source/reference.
    """
    p=Path(verification_csv)
    if not p.exists():
        raise FileNotFoundError(str(p))
    f=pd.read_csv(p,dtype=str).fillna("")
    required={
        "queue_event_id","code","candidate_cash_amount","known_at",
        "market_ex_date","market_source","market_reference","market_source_url",
    }
    missing=required-set(f.columns)
    if missing:
        raise ValueError("market ex-date verification CSV 누락 열: "+", ".join(sorted(missing)))

    f["market_ex_date"]=f["market_ex_date"].map(_clean_date)
    f["known_at"]=f["known_at"].map(_clean_date)
    f["candidate_cash_amount"]=pd.to_numeric(
        f["candidate_cash_amount"].astype(str).str.replace(",","",regex=False),
        errors="coerce"
    )

    invalid=(
        f["queue_event_id"].str.strip().eq("")
        | f["market_ex_date"].str.len().ne(8)
        | f["market_ex_date"].gt(RESEARCH_SEEN_THROUGH)
        | f["known_at"].str.len().ne(8)
        | f["known_at"].gt(f["market_ex_date"])
        | f["candidate_cash_amount"].isna()
        | f["candidate_cash_amount"].le(0)
        | f["market_source"].str.strip().eq("")
        | f["market_source"].str.contains(PLACEHOLDER)
        | f["market_reference"].str.strip().eq("")
    )

    audit=f[[
        "queue_event_id","code","market_ex_date","known_at",
        "candidate_cash_amount","market_source","market_reference",
    ]].copy()
    audit["valid"]=~invalid
    audit["error"]=invalid.map(lambda x:"INVALID_OFFICIAL_MARKET_EXDATE" if x else "")
    ap=Path(audit_csv); ap.parent.mkdir(parents=True,exist_ok=True)
    audit.to_csv(ap,index=False,encoding="utf-8-sig")

    valid=f[~invalid].copy()
    strict=pd.DataFrame({
        "queue_event_id":valid["queue_event_id"],
        "code":valid["code"].astype(str).str.zfill(6),
        "event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":valid["record_date"] if "record_date" in valid.columns else "",
        "effective_date":valid["market_ex_date"],
        "known_at":valid["known_at"],
        "action_type":valid["action_type"] if "action_type" in valid.columns else "CASH_DIVIDEND",
        "adjustment_factor":1.0,
        "cash_amount":valid["candidate_cash_amount"],
        "verification_source":valid["market_source"],
        "verification_reference":valid["market_reference"],
        "resolution_note":"STRICT_OFFICIAL_MARKET_EXDATE",
    })
    op=Path(strict_evidence_csv); op.parent.mkdir(parents=True,exist_ok=True)
    strict.to_csv(op,index=False,encoding="utf-8-sig")

    return {
        "input_rows":int(len(f)),
        "strict_rows":int(len(strict)),
        "invalid_rows":int(invalid.sum()),
        "strict_evidence_csv":str(op),
        "audit_csv":str(ap),
    }


def summarize_kodex_high_signal_bodies_v321(
    *,
    response_audit_csv: str,
    field_candidates_csv: str,
    output_json: str,
) -> dict:
    """Summarize why KODEX bodies did/did not yield structured distribution fields."""
    audit=pd.read_csv(response_audit_csv,dtype=str).fillna("")
    fields=pd.read_csv(field_candidates_csv,dtype=str).fillna("")
    payload={
        "phase":"V3.2.1 Phase 5.15",
        "responses":int(len(audit)),
        "status_counts":{str(k):int(v) for k,v in audit.get("status",pd.Series(dtype=str)).value_counts().to_dict().items()},
        "content_type_counts":{str(k):int(v) for k,v in audit.get("content_type",pd.Series(dtype=str)).value_counts().to_dict().items()},
        "responses_with_date_fields":int((pd.to_numeric(audit.get("date_fields",0),errors="coerce").fillna(0)>0).sum()) if not audit.empty else 0,
        "responses_with_amount_fields":int((pd.to_numeric(audit.get("amount_fields",0),errors="coerce").fillna(0)>0).sum()) if not audit.empty else 0,
        "field_candidate_rows":int(len(fields)),
        "research_seen_through":RESEARCH_SEEN_THROUGH,
        "next_action":"Inspect exact high-signal URLs/response bodies; current bodies contain no strict date+amount distribution schema.",
    }
    op=Path(output_json); op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return payload|{"output_json":str(op)}
