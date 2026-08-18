from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.ml.phase529_kind_market_search_v321 import CONTENTS_URL, EXTERNAL_RE, MAIN_URL, SEARCH_URL, VIEWER_URL


def discover_historical_kind_exdates_v321(
    dart_client, *, candidates_csv: str, output_csv: str, audit_csv: str,
    timeout: int = 20, session=None,
) -> dict:
    candidates = pd.read_csv(candidates_csv, dtype=str).fillna("")
    targets = candidates[candidates["candidate_status"].eq("READY_FOR_OFFICIAL_MARKET_VERIFICATION")].copy()
    names = dart_client.stock_name_map()
    http = session or requests.Session()
    http.headers.update({"User-Agent": "Mozilla/5.0"})
    http.get(MAIN_URL, timeout=timeout).raise_for_status()
    rows, audits = [], []
    for item in targets.itertuples(index=False):
        code = str(item.code).zfill(6); company = names.get(code, "")
        candidate = str(item.calendar_prior_trading_day_1)
        center = datetime.strptime(candidate, "%Y%m%d")
        start, end = center - timedelta(days=3), center + timedelta(days=1)
        response = http.post(SEARCH_URL, data={
            "method": "searchTotalInfoSub", "forward": "searchtotalinfo_detail",
            "fdName": "all_mktact_idx", "pageIndex": "1", "currentPageSize": "100",
            "scn": "mktact", "srchFd": "2", "kwd": "배당락 기준 가격 안내",
            "fromData": start.strftime("%Y-%m-%d"), "toData": end.strftime("%Y-%m-%d"),
        }, headers={"X-Requested-With": "XMLHttpRequest", "Referer": MAIN_URL}, timeout=timeout)
        response.raise_for_status()
        if (response.encoding or "").lower() == "iso-8859-1" and response.apparent_encoding:
            response.encoding = response.apparent_encoding
        notices = []
        for node in BeautifulSoup(response.text, "html.parser").select("dt.img"):
            link = node.select_one("span.subject a")
            if not link:
                continue
            title = " ".join(link.get_text(" ", strip=True).split())
            ids = re.findall(r"\d{14}", link.get("onclick", ""))
            if "배당락" in title and len(ids) >= 2:
                notices.append((title, ids[0], ids[1]))
        matched = []
        for title, acpt, doc in notices:
            viewer, source_url, body = VIEWER_URL.format(acpt), "", ""
            try:
                http.get(viewer, timeout=timeout).raise_for_status()
                contents = http.get(CONTENTS_URL.format(doc), headers={"Referer": viewer}, timeout=timeout)
                contents.raise_for_status()
                urls = EXTERNAL_RE.findall(contents.text)
                source_url = urls[0] if urls else ""
                source = http.get(source_url, headers={"Referer": viewer}, timeout=timeout) if source_url else contents
                source.raise_for_status()
                if (source.encoding or "").lower() == "iso-8859-1" and source.apparent_encoding:
                    source.encoding = source.apparent_encoding
                body = " ".join(BeautifulSoup(source.text, "html.parser").get_text(" ", strip=True).split())
            except requests.RequestException:
                continue
            normalized = re.sub(r"\s+", "", body)
            if company and re.sub(r"\s+", "", company) in normalized:
                matched.append((title, acpt, doc, source_url or viewer))
        status = "DISCOVERED_OFFICIAL_NOTICE" if len(matched) == 1 else (
            "AMBIGUOUS_OFFICIAL_NOTICES" if len(matched) > 1 else "NO_MATCHING_OFFICIAL_NOTICE")
        if len(matched) == 1:
            title, acpt, doc, url = matched[0]
            rows.append({
                "queue_event_id": item.queue_event_id, "code": code, "company_name": company,
                "candidate_ex_date": candidate, "notice_title": title,
                "kind_acpt_no": acpt, "kind_doc_no": doc, "market_source_url": url,
                "discovery_status": status, "strict_promotion_status": "NOT_PROMOTED_NOTICE_BODY_PARSE_REQUIRED",
            })
        audits.append({
            "queue_event_id": item.queue_event_id, "code": code, "company_name": company,
            "candidate_ex_date": candidate, "search_start": start.strftime("%Y%m%d"),
            "search_end": end.strftime("%Y%m%d"), "notices_examined": len(notices),
            "matching_notices": len(matched), "status": status,
        })
    columns = ["queue_event_id", "code", "company_name", "candidate_ex_date", "notice_title",
               "kind_acpt_no", "kind_doc_no", "market_source_url", "discovery_status", "strict_promotion_status"]
    output = pd.DataFrame(rows, columns=columns)
    op, ap = Path(output_csv), Path(audit_csv); op.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(op, index=False, encoding="utf-8-sig")
    audit = pd.DataFrame(audits); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    return {"target_rows": len(targets), "discovered_rows": len(output),
            "unmatched_rows": int((audit["status"] == "NO_MATCHING_OFFICIAL_NOTICE").sum()),
            "ambiguous_rows": int((audit["status"] == "AMBIGUOUS_OFFICIAL_NOTICES").sum()),
            "output_csv": str(op), "audit_csv": str(ap)}
