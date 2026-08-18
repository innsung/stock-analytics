
from __future__ import annotations

from pathlib import Path
import re
import time
from html import unescape
import pandas as pd
import requests

from src.kind_service import is_krx_failover_url

KIND_VIEWER = "https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={rcept_no}"
KIND_SEARCH = "https://kind.krx.co.kr/disclosure/searchdisclosurebycorp.do"
KIND_DOC_VALUE_RE = re.compile(r"(?P<doc_no>\d{14})\s*\|\s*[YN]", re.I)
KIND_SEARCH_RESULT_RE = re.compile(
    r"openDisclsViewer\('(?P<acpt_no>\d{14})','[^']*'\)[^>]*"
    r"title=['\"](?P<title>[^'\"]*)['\"]",
    re.I,
)
KIND_DOCUMENT_URL_RE = re.compile(
    r"parent\.setPath\(\s*['\"][^'\"]*['\"]\s*,\s*"
    r"['\"](?P<url>https?://kind\.krx\.co\.kr/external/[^'\"]+)['\"]",
    re.I,
)
DATE_RE = re.compile(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})")

def _date(s):
    v = re.sub(r"[^0-9]", "", str(s or ""))
    return v if len(v) == 8 else ""

def _extract_labeled_date(text: str, labels: tuple[str, ...]) -> str:
    compact = re.sub(r"\s+", " ", text)
    for label in labels:
        for m in re.finditer(re.escape(label), compact):
            ctx = compact[m.start():m.start()+220]
            dm = DATE_RE.search(ctx)
            if dm:
                return f"{int(dm.group(1)):04d}{int(dm.group(2)):02d}{int(dm.group(3)):02d}"
    return ""

def _extract_cash_amount(text: str):
    compact = re.sub(r"\s+", " ", text)
    for label in ("1주당 배당금", "주당 배당금", "1주당배당금"):
        m = re.search(re.escape(label) + r".{0,120}?([0-9][0-9,]*(?:\.[0-9]+)?)\s*원?", compact)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except Exception:
                pass
    return None

def _extract_kind_doc_no(html: str) -> str:
    """Extract the disclosure docNo embedded in a KIND viewer response."""
    if not html:
        return ""

    text = unescape(str(html))
    selected = re.search(r"<option\b(?=[^>]*\bselected\b)[^>]*>", text, re.I)
    if selected:
        value = re.search(r"\bvalue\s*=\s*['\"](?P<value>[^'\"]+)['\"]", selected.group(0), re.I)
        if value:
            match = KIND_DOC_VALUE_RE.search(value.group("value"))
            if match:
                return match.group("doc_no")

    match = KIND_DOC_VALUE_RE.search(text)
    return match.group("doc_no") if match else ""


def _extract_kind_document_url(html: str) -> str:
    if not html:
        return ""
    match = KIND_DOCUMENT_URL_RE.search(unescape(str(html)))
    return match.group("url") if match else ""


def _search_kind_disclosures(
    session: requests.Session,
    *,
    code: str,
    disclosure_date: str,
    timeout: float,
) -> list[dict[str, str]]:
    """Search KIND and initialize the session required by the disclosure viewer."""
    normalized_date = _date(disclosure_date)
    if not normalized_date:
        return []
    date_value = f"{normalized_date[:4]}-{normalized_date[4:6]}-{normalized_date[6:]}"
    response = session.post(
        KIND_SEARCH,
        data={
            "method": "searchDisclosureByCorpSub",
            "forward": "searchdisclosurebycorp_sub",
            "currentPageSize": "100",
            "pageIndex": "1",
            "orderIndex": "1",
            "orderMode": "D",
            "fromDate": date_value,
            "toDate": date_value,
            "repIsuSrtCd": "A" + str(code).zfill(6),
            "allRepIsuSrtCd": "",
            "searchCorpName": "",
            "reportNm": "",
            "reportCd": "",
            "lastReport": "",
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": KIND_SEARCH + "?method=searchDisclosureByCorpMain",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return [
        {
            "kind_acpt_no": match.group("acpt_no"),
            "title": unescape(match.group("title")).strip(),
        }
        for match in KIND_SEARCH_RESULT_RE.finditer(response.text)
    ]


def crosscheck_kind_dividend_disclosures_v321(
    *,
    market_exdate_queue_csv: str,
    output_csv: str,
    audit_csv: str,
    timeout_seconds: float = 15.0,
) -> dict:
    p = Path(market_exdate_queue_csv)
    if not p.exists():
        raise FileNotFoundError(str(p))
    q = pd.read_csv(p, dtype=str).fillna("")
    required = {
        "queue_event_id","code","candidate_cash_amount","record_date",
        "known_at","official_document_reference","priority"
    }
    miss = required - set(q.columns)
    if miss:
        raise ValueError("market ex-date queue 누락 열: " + ", ".join(sorted(miss)))

    sess = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    rows, audits = [], []
    search_cache: dict[tuple[str, str], list[dict[str, str]]] = {}
    targets = q[q["priority"].eq("P1_RECORD_DATE_READY_FOR_MARKET_VERIFICATION")].copy()

    for _, r in targets.iterrows():
        rcept = str(r["official_document_reference"]).strip()
        status, error, url = "NO_RECEIPT_NO", "", ""
        retryable, http_status, final_url = False, "", ""
        kind_record, kind_amount, pay_date, board_date = "", None, "", ""
        kind_doc_no = ""
        kind_document_url = ""
        kind_disclosure_title = ""
        if rcept:
            url = KIND_VIEWER.format(rcept_no=rcept)
            try:
                search_key = (str(r["code"]).zfill(6), _date(r["known_at"]))
                if search_key not in search_cache:
                    search_cache[search_key] = _search_kind_disclosures(
                        sess,
                        code=search_key[0],
                        disclosure_date=search_key[1],
                        timeout=timeout_seconds,
                    )
                candidates = search_cache[search_key]
                matched = next(
                    (item for item in candidates if item["kind_acpt_no"] == rcept),
                    None,
                )
                if matched is None:
                    dividend_candidates = [
                        item for item in candidates
                        if "현금ㆍ현물배당결정" in re.sub(r"\s+", "", item["title"])
                    ]
                    matched = dividend_candidates[0] if len(dividend_candidates) == 1 else None
                if matched is None:
                    status = "KIND_REFERENCE_UNRESOLVED"
                    error = "No unique KIND dividend disclosure matched code and disclosure date"
                    raise LookupError(error)
                rcept = matched["kind_acpt_no"]
                kind_disclosure_title = matched["title"]
                url = KIND_VIEWER.format(rcept_no=rcept)
                resp = sess.get(url, timeout=timeout_seconds, headers=headers, allow_redirects=True)
                http_status = str(resp.status_code)
                final_url = resp.url or url
                resp.raise_for_status()
                if is_krx_failover_url(final_url):
                    status = "KRX_SERVICE_UNAVAILABLE"
                    retryable = True
                    error = "KRX redirected request to upgrade/failover service"
                    raise RuntimeError(error)
                text = resp.text
                kind_doc_no = _extract_kind_doc_no(text)
                if not kind_doc_no:
                    status = "KIND_DOCUMENT_UNAVAILABLE"
                    error = "KIND viewer returned no mainDoc/docNo for the supplied reference"
                    continue_parsing = False
                else:
                    continue_parsing = True
                    contents = sess.get(
                        "https://kind.krx.co.kr/common/disclsviewer.do",
                        params={"method": "searchContents", "docNo": kind_doc_no},
                        headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
                        timeout=timeout_seconds,
                    )
                    contents.raise_for_status()
                    kind_document_url = _extract_kind_document_url(contents.text)
                    if not kind_document_url:
                        status = "KIND_DOCUMENT_PATH_UNAVAILABLE"
                        error = "KIND searchContents returned no external document URL"
                        continue_parsing = False
                kind_record = _extract_labeled_date(text, ("배당기준일", "배당 기준일"))
                pay_date = _extract_labeled_date(text, ("배당금지급 예정일자", "배당금 지급 예정일자", "지급 예정일"))
                board_date = _extract_labeled_date(text, ("이사회결의일", "결정일"))
                kind_amount = _extract_cash_amount(text)
                if continue_parsing:
                    status = "OK"
            except Exception as exc:
                if status not in {"KRX_SERVICE_UNAVAILABLE", "KIND_REFERENCE_UNRESOLVED"}:
                    status = "FAILED"
                    retryable = True
                    error = f"{type(exc).__name__}: {exc}"

        try:
            expected_amount = float(str(r["candidate_cash_amount"]).replace(",", ""))
        except Exception:
            expected_amount = None
        amount_match = kind_amount is not None and expected_amount is not None and abs(kind_amount - expected_amount) < 1e-9
        record_match = bool(kind_record and kind_record == _date(r["record_date"]))

        rows.append({
            "queue_event_id": r["queue_event_id"],
            "code": str(r["code"]).zfill(6),
            "dart_record_date": _date(r["record_date"]),
            "kind_record_date": kind_record,
            "candidate_cash_amount": expected_amount,
            "kind_cash_amount": kind_amount,
            "kind_pay_date": pay_date,
            "kind_board_date": board_date,
            "record_date_match": record_match,
            "cash_amount_match": amount_match,
            "kind_url": url,
            "kind_acpt_no": rcept,
            "kind_doc_no": kind_doc_no,
            "kind_document_url": kind_document_url,
            "kind_disclosure_title": kind_disclosure_title,
            "kind_status": status,
            "kind_retryable": retryable,
            "kind_http_status": http_status,
            "kind_final_url": final_url,
            "kind_fetch_error": error,
            "promotion_status": "KIND_CROSSCHECK_ONLY_NOT_EXDATE_EVIDENCE",
        })
        audits.append({
            "queue_event_id": r["queue_event_id"],
            "kind_acpt_no": rcept,
            "kind_doc_no": kind_doc_no,
            "kind_document_url": kind_document_url,
            "kind_disclosure_title": kind_disclosure_title,
            "status": status,
            "retryable": retryable,
            "http_status": http_status,
            "final_url": final_url,
            "error": error,
        })
        time.sleep(0.05)

    out = pd.DataFrame(rows)
    audit = pd.DataFrame(audits)
    op, ap = Path(output_csv), Path(audit_csv)
    op.parent.mkdir(parents=True, exist_ok=True)
    ap.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(op, index=False, encoding="utf-8-sig")
    audit.to_csv(ap, index=False, encoding="utf-8-sig")

    return {
        "p1_rows": int(len(targets)),
        "kind_success": int((out["kind_status"] == "OK").sum()) if not out.empty else 0,
        "record_matches": int(out["record_date_match"].astype(str).str.lower().eq("true").sum()) if not out.empty else 0,
        "amount_matches": int(out["cash_amount_match"].astype(str).str.lower().eq("true").sum()) if not out.empty else 0,
        "output_csv": str(op),
        "audit_csv": str(ap),
    }

def discover_kodex_next_hops_v321(*, bodies_dir: str, output_csv: str) -> dict:
    root = Path(bodies_dir)
    if not root.exists():
        raise FileNotFoundError(str(root))
    patterns = [
        re.compile(r'''(?:url|action)\s*[:=]\s*["']([^"']+)["']''', re.I),
        re.compile(r'''["'](/[^"']*(?:api|ajax|etf|product|dist|dividend)[^"']*)["']''', re.I),
        re.compile(r'''fetch\(\s*["']([^"']+)["']''', re.I),
        re.compile(r'''\$\.ajax\([^)]*url\s*:\s*["']([^"']+)["']''', re.I | re.S),
    ]
    rows = []
    files = [p for p in sorted(root.glob("*")) if p.is_file()]
    for p in files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in patterns:
            for m in pat.finditer(text):
                raw = m.group(1).strip()
                ctx = re.sub(r"\s+", " ", text[max(0, m.start()-180):m.end()+220])[:500]
                score = sum(
                    1 for k in ("분배금","distribution","dividend","dist","etf","product","ajax","api")
                    if k.lower() in (raw + " " + ctx).lower()
                )
                rows.append({
                    "body_file": str(p),
                    "next_hop": raw,
                    "score": score,
                    "context": ctx,
                    "promotion_status": "DISCOVERY_ONLY",
                })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["score","next_hop"], ascending=[False, True]).drop_duplicates(["next_hop"])
    op = Path(output_csv)
    op.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(op, index=False, encoding="utf-8-sig")
    return {"body_files": len(files), "next_hops": int(len(out)), "output_csv": str(op)}
