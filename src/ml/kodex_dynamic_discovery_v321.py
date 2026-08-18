
from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin, urlparse
import json
import re

import pandas as pd
import requests

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

KEYWORDS = (
    "distribution", "dividend", "분배금", "지급현황", "bunbae", "dist",
    "ajax", "api", "etf", "product",
)
URL_PATTERNS = [
    re.compile(r'["\']((?:https?:)?//[^"\' ]+)["\']', re.I),
    re.compile(r'["\'](/[^"\' ]+)["\']'),
    re.compile(r'url\s*[:=]\s*["\']([^"\']+)["\']', re.I),
]


def _same_origin(base: str, candidate: str) -> bool:
    b = urlparse(base)
    c = urlparse(candidate)
    return (not c.netloc) or (c.netloc == b.netloc)


def _score(text: str) -> int:
    low = text.lower()
    return sum(1 for k in KEYWORDS if k.lower() in low)


def discover_kodex_dynamic_endpoints_v321(
    *,
    product_url: str,
    output_dir: str,
    timeout_seconds: float = 30.0,
    max_scripts: int = 40,
) -> dict:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    sess = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    r = sess.get(product_url, timeout=timeout_seconds, headers=headers)
    r.raise_for_status()
    html = r.text
    (target / "kodex_product_page_phase511.html").write_text(html, encoding="utf-8")

    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I)
    script_urls = []
    for src in script_srcs:
        u = urljoin(product_url, src)
        if _same_origin(product_url, u) and u not in script_urls:
            script_urls.append(u)
    script_urls = script_urls[:max_scripts]

    documents = [("HTML", product_url, html)]
    script_audit = []
    for u in script_urls:
        try:
            sr = sess.get(u, timeout=timeout_seconds, headers=headers)
            sr.raise_for_status()
            text = sr.text
            documents.append(("JS", u, text))
            script_audit.append({"url": u, "status": "OK", "bytes": len(text), "error": ""})
        except Exception as exc:
            script_audit.append({
                "url": u, "status": "FAILED", "bytes": 0,
                "error": f"{type(exc).__name__}: {exc}",
            })

    candidates = {}
    for kind, doc_url, text in documents:
        for pat in URL_PATTERNS:
            for m in pat.finditer(text):
                raw = m.group(1).strip()
                if raw.startswith("javascript:") or raw.startswith("#"):
                    continue
                full = urljoin(doc_url, raw)
                if not _same_origin(product_url, full):
                    continue
                context = text[max(0, m.start() - 220):min(len(text), m.end() + 220)]
                score = _score(raw + " " + context)
                if score <= 0:
                    continue
                rec = candidates.get(full, {
                    "url": full, "score": 0, "hits": 0, "sources": set(), "contexts": []
                })
                rec["score"] = max(rec["score"], score)
                rec["hits"] += 1
                rec["sources"].add(doc_url)
                if len(rec["contexts"]) < 3:
                    rec["contexts"].append(re.sub(r"\s+", " ", context)[:500])
                candidates[full] = rec

    rows = []
    for rec in sorted(candidates.values(), key=lambda x: (-x["score"], -x["hits"], x["url"])):
        rows.append({
            "url": rec["url"],
            "score": rec["score"],
            "hits": rec["hits"],
            "sources": "|".join(sorted(rec["sources"])),
            "context": " || ".join(rec["contexts"]),
            "probe_status": "NOT_PROBED",
            "promotion_status": "DISCOVERY_ONLY_NOT_EVENT_EVIDENCE",
        })

    endpoint_csv = target / "kodex_dynamic_endpoint_candidates_v321.csv"
    pd.DataFrame(rows).to_csv(endpoint_csv, index=False, encoding="utf-8-sig")
    script_audit_csv = target / "kodex_dynamic_script_audit.csv"
    pd.DataFrame(script_audit).to_csv(script_audit_csv, index=False, encoding="utf-8-sig")

    manifest = {
        "phase": "V3.2.1 Phase 5.11",
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "product_url": product_url,
        "scripts_discovered": len(script_srcs),
        "scripts_scanned": len(script_urls),
        "endpoint_candidates": len(rows),
        "status": "DYNAMIC_ENDPOINT_DISCOVERY_COMPLETED",
        "note": "No discovered endpoint is treated as official event evidence until separately verified.",
        "outputs": {
            "endpoint_candidates": str(endpoint_csv),
            "script_audit": str(script_audit_csv),
        },
    }
    mp = target / "kodex_dynamic_discovery_manifest.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest | {"manifest_path": str(mp)}


def refine_stock_dividend_candidates_v321(
    *,
    dividend_facts_csv: str,
    verification_csv: str,
    output_csv: str,
    audit_csv: str,
    etf_codes: list[str] | None = None,
) -> dict:
    etf_codes = {str(x).zfill(6) for x in (etf_codes or ["069500"])}
    facts = pd.read_csv(dividend_facts_csv, dtype=str).fillna("")
    ver = pd.read_csv(verification_csv, dtype=str).fillna("")
    required = {"code", "business_year", "disclosed_at", "se", "stock_knd", "thstrm", "source"}
    missing = required - set(facts.columns)
    if missing:
        raise ValueError("배당 fact 누락 열: " + ", ".join(sorted(missing)))
    required_v = {"queue_event_id", "code", "event_family", "source_reference_date"}
    missing = required_v - set(ver.columns)
    if missing:
        raise ValueError("verification CSV 누락 열: " + ", ".join(sorted(missing)))

    def is_cash(label: str) -> bool:
        s = re.sub(r"\s+", "", str(label))
        return (
            "주당현금배당금" in s
            or "주당현금배당" in s
            or ("주당" in s and "배당금" in s and "현금" in s)
        )

    def common(kind: str) -> bool:
        s = str(kind).lower()
        return (not s) or any(x in s for x in ("보통", "common", "ordinary"))

    def number(v):
        s = str(v).replace(",", "").replace("원", "").strip()
        if s in {"", "-"}:
            return None
        try:
            x = float(s)
            return x if x > 0 else None
        except Exception:
            return None

    facts["code"] = facts["code"].astype(str).str.zfill(6)
    facts = facts[~facts["code"].isin(etf_codes)]
    facts = facts[facts["se"].map(is_cash) & facts["stock_knd"].map(common)].copy()
    facts["amount"] = facts["thstrm"].map(number)
    facts = facts[facts["amount"].notna()].copy()

    q = ver[
        ver["event_family"].astype(str).str.upper().eq("DIVIDEND_OR_DISTRIBUTION")
        & ~ver["code"].astype(str).str.zfill(6).isin(etf_codes)
    ].drop_duplicates("queue_event_id").copy()
    q["code"] = q["code"].astype(str).str.zfill(6)

    out_rows = []
    audit = []
    for _, row in q.iterrows():
        code = row["code"]
        ref = str(row["source_reference_date"])
        years = []
        if len(ref) == 8 and ref.isdigit():
            y = int(ref[:4])
            years = [str(y - 1), str(y)]

        chosen = None
        chosen_year = ""
        fallback = False
        ambiguous_count = 0

        for yi, year in enumerate(years):
            m = facts[
                facts["code"].eq(code)
                & facts["business_year"].astype(str).eq(year)
            ].copy()
            vals = sorted(set(m["amount"].astype(float).round(12)))
            if len(vals) == 1:
                chosen = m.iloc[0]
                chosen_year = year
                fallback = yi == 1
                break
            if len(vals) > 1:
                chosen_year = year
                ambiguous_count = len(vals)
                break

        status = "NO_AMOUNT_CANDIDATE"
        if isinstance(chosen, pd.Series):
            status = (
                "UNIQUE_AMOUNT_CANDIDATE_FALLBACK_YEAR"
                if fallback else "UNIQUE_AMOUNT_CANDIDATE_PRIMARY_YEAR"
            )
            out_rows.append({
                "queue_event_id": row["queue_event_id"],
                "code": code,
                "source_reference_date": ref,
                "selected_business_year": chosen_year,
                "candidate_cash_amount": float(chosen["amount"]),
                "candidate_known_at": str(chosen["disclosed_at"]),
                "candidate_source": str(chosen["source"]),
                "candidate_reference": f"OpenDART annual dividend fact:{chosen_year}",
                "selection_rule": "REFERENCE_YEAR_MINUS_ONE_THEN_REFERENCE_YEAR",
                "promotion_status": "AMOUNT_ONLY_NEEDS_OFFICIAL_EX_DATE",
            })
        elif ambiguous_count:
            status = f"AMBIGUOUS_WITHIN_BUSINESS_YEAR:{ambiguous_count}"

        audit.append({
            "queue_event_id": row["queue_event_id"],
            "code": code,
            "source_reference_date": ref,
            "preferred_year": years[0] if years else "",
            "fallback_year": years[1] if len(years) > 1 else "",
            "selected_year": chosen_year,
            "status": status,
        })

    out = pd.DataFrame(out_rows)
    a = pd.DataFrame(audit)
    op = Path(output_csv)
    ap = Path(audit_csv)
    op.parent.mkdir(parents=True, exist_ok=True)
    ap.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(op, index=False, encoding="utf-8-sig")
    a.to_csv(ap, index=False, encoding="utf-8-sig")
    counts = a["status"].value_counts().to_dict() if not a.empty else {}
    return {
        "queue_rows": int(len(a)),
        "candidate_rows": int(len(out)),
        "status_counts": {str(k): int(v) for k, v in counts.items()},
        "output_csv": str(op),
        "audit_csv": str(ap),
    }
