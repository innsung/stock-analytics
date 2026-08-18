from __future__ import annotations

from pathlib import Path
import json
import re
from datetime import datetime
from html import unescape

import pandas as pd
import requests

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

DEFAULT_URL = "https://m.samsungfund.com/etf/product/view.do?id=2ETF01"


def _clean_date(v: str) -> str:
    s = re.sub(r"[^0-9]", "", str(v or ""))
    if len(s) == 8:
        return s
    return ""


def _clean_amount(v: str) -> float | None:
    s = re.sub(r"[^0-9.\-]", "", str(v or ""))
    if not s:
        return None
    try:
        x = float(s)
        return x if x > 0 else None
    except Exception:
        return None


def acquire_kodex_distribution_candidates_v321(
    *,
    output_dir: str,
    url: str = DEFAULT_URL,
    timeout_seconds: float = 30.0,
) -> dict:
    """Fetch the official KODEX product page and parse actual distribution rows.

    Policy text is never converted into events. Only table-like rows containing
    both a concrete calendar date and a positive per-unit cash amount are emitted.
    The raw HTML is saved for audit.
    """
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=timeout_seconds, headers={"User-Agent":"Mozilla/5.0"})
    resp.raise_for_status()
    html = resp.text
    raw_path = target / "kodex_069500_product_page.html"
    raw_path.write_text(html, encoding="utf-8")

    text = unescape(re.sub(r"<[^>]+>", " ", html))
    text = re.sub(r"\s+", " ", text)

    # Conservative parser: look for date + won amount in short local spans.
    # It intentionally ignores generic policy phrases such as "1월, 4월, 7월, 10월".
    rows = []
    seen = set()
    date_pat = re.compile(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})")
    for m in date_pat.finditer(text):
        y, mo, d = map(int, m.groups())
        try:
            dt = datetime(y, mo, d)
        except ValueError:
            continue
        date = dt.strftime("%Y%m%d")
        if date > RESEARCH_SEEN_THROUGH:
            continue
        span = text[max(0,m.start()-120):min(len(text),m.end()+180)]
        # Require explicit distribution context near the date.
        if "분배금" not in span:
            continue
        amounts = re.findall(r"(?:좌당|1좌당|분배금)[^0-9]{0,20}([0-9][0-9,]*)\s*원", span)
        for a in amounts:
            amt = _clean_amount(a)
            if amt is None:
                continue
            key=(date,amt)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "code":"069500",
                "candidate_date":date,
                "cash_amount":amt,
                "verification_source":"SAMSUNG_KODEX_PRODUCT_PAGE",
                "verification_reference":"2ETF01",
                "source_url":url,
                "strict_ready":False,
                "strict_block_reason":"ANNOUNCED_AT_AND_EX_DATE_ROLE_NOT_VERIFIED",
                "context":span[:300],
            })

    frame=pd.DataFrame(rows)
    csv_path=target/"kodex_069500_distribution_candidates_v321.csv"
    frame.to_csv(csv_path,index=False,encoding="utf-8-sig")
    manifest={
        "phase":"V3.2.1 Phase 5.10",
        "source_url":url,
        "research_seen_through":RESEARCH_SEEN_THROUGH,
        "candidate_rows":int(len(frame)),
        "status":"KODEX_DISTRIBUTION_CANDIDATES_ACQUIRED",
        "note":"Only concrete date+cash rows are candidates; policy dates are ignored.",
        "outputs":{"raw_html":str(raw_path),"candidates":str(csv_path)},
    }
    mp=target/"kodex_069500_distribution_candidate_manifest.json"
    mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest|{"manifest_path":str(mp)}


def build_stock_dividend_ambiguity_report_v321(
    *, amount_audit_csv: str, amount_candidates_csv: str, output_csv: str
) -> dict:
    """Create an actionable report for the 37/74/33 stock-dividend split."""
    audit=pd.read_csv(amount_audit_csv,dtype=str).fillna("")
    cand=pd.read_csv(amount_candidates_csv,dtype=str).fillna("")
    rows=[]
    for _,r in audit.iterrows():
        qid=r.get("queue_event_id","")
        c=cand[cand["queue_event_id"].eq(qid)] if "queue_event_id" in cand.columns else cand.iloc[0:0]
        rows.append({
            "queue_event_id":qid,
            "code":str(r.get("code","")).zfill(6),
            "source_reference_date":r.get("source_reference_date",""),
            "current_status":r.get("status",""),
            "candidate_cash_amounts":"|".join(c.get("candidate_cash_amount",pd.Series(dtype=str)).astype(str).tolist()),
            "next_required_evidence":(
                "OFFICIAL_EX_DATE_AND_AMOUNT" if r.get("status","")=="UNIQUE_AMOUNT_CANDIDATE"
                else "DISAMBIGUATE_AMOUNT_AND_OFFICIAL_EX_DATE"
                if str(r.get("status","")).startswith("AMBIGUOUS")
                else "FIND_OFFICIAL_AMOUNT_AND_EX_DATE"
            ),
        })
    out=pd.DataFrame(rows)
    p=Path(output_csv); p.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(p,index=False,encoding="utf-8-sig")
    return {
        "rows":int(len(out)),
        "unique":int((out["current_status"]=="UNIQUE_AMOUNT_CANDIDATE").sum()),
        "ambiguous":int(out["current_status"].str.startswith("AMBIGUOUS").sum()),
        "missing":int((out["current_status"]=="NO_AMOUNT_CANDIDATE").sum()),
        "output_csv":str(p),
    }
