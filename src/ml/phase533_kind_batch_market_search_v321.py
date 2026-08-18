from __future__ import annotations

from datetime import date
from pathlib import Path
import calendar
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.ml.phase529_kind_market_search_v321 import (
    CONTENTS_URL, EXTERNAL_RE, MAIN_URL, SEARCH_URL, VIEWER_URL,
)


def _months(start: str, end: str):
    current = date(int(start[:4]), int(start[4:6]), 1)
    finish = date(int(end[:4]), int(end[4:6]), int(end[6:8]))
    while current <= finish:
        last = min(date(current.year, current.month, calendar.monthrange(current.year, current.month)[1]), finish)
        yield current.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)


def discover_kind_market_notices_batch_v321(
    *, acquisition_manifest_csv: str, output_csv: str, audit_csv: str,
    search_start: str = "20260101", search_end: str = "20260709", timeout: int = 20,
) -> dict:
    manifest = pd.read_csv(acquisition_manifest_csv, dtype=str).fillna("")
    required = {"code", "flr_nm", "acquisition_status"}
    missing = required - set(manifest.columns)
    if missing:
        raise ValueError("acquisition manifest missing columns: " + ", ".join(sorted(missing)))
    targets = manifest[manifest["acquisition_status"].eq("READY_FOR_KIND_MARKET_SEARCH")]
    names = {r["flr_nm"]: str(r["code"]).zfill(6) for _, r in targets.iterrows() if r["flr_nm"]}
    session = requests.Session(); session.headers.update({"User-Agent": "Mozilla/5.0"})
    session.get(MAIN_URL, timeout=timeout).raise_for_status()
    matches: dict[tuple[str, str], dict] = {}
    month_audits = []
    for start, end in _months(search_start, search_end):
        response = session.post(SEARCH_URL, data={
            "method": "searchTotalInfoSub", "forward": "searchtotalinfo_detail",
            "fdName": "all_mktact_idx", "pageIndex": "1", "currentPageSize": "100",
            "scn": "mktact", "srchFd": "2", "kwd": "배당락 기준 가격 안내",
            "fromData": start, "toData": end,
        }, headers={"X-Requested-With": "XMLHttpRequest", "Referer": MAIN_URL}, timeout=timeout)
        response.raise_for_status()
        if (response.encoding or "").lower() == "iso-8859-1" and response.apparent_encoding:
            response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        entries = soup.select("dt.img")
        for item in entries:
            name_node, link = item.select_one("strong.name"), item.select_one("span.subject a")
            if not name_node or not link:
                continue
            company = " ".join(name_node.get_text(" ", strip=True).split())
            if company not in names:
                continue
            title = " ".join(link.get_text(" ", strip=True).split())
            ids = re.findall(r"\d{14}", link.get("onclick", ""))
            if "배당락" not in title or len(ids) < 2:
                continue
            # A title ending in 안내 is the common-share notice. Share-class
            # suffixes (우, 우B, etc.) are retained in audit but not promoted.
            common_share = title.rstrip().endswith("안내")
            matches[(ids[0], ids[1])] = {
                "code": names[company], "company_name": company, "notice_title": title,
                "kind_acpt_no": ids[0], "kind_doc_no": ids[1], "common_share": common_share,
                "search_window_start": start, "search_window_end": end,
            }
        month_audits.append({"search_window_start": start, "search_window_end": end,
                             "returned_entries": len(entries), "http_status": response.status_code})

    rows = []
    for row in matches.values():
        source_url, error = "", ""
        if row["common_share"]:
            try:
                viewer = VIEWER_URL.format(row["kind_acpt_no"])
                session.get(viewer, timeout=timeout).raise_for_status()
                contents = session.get(CONTENTS_URL.format(row["kind_doc_no"]),
                                       headers={"Referer": viewer}, timeout=timeout)
                contents.raise_for_status()
                urls = EXTERNAL_RE.findall(contents.text)
                source_url = urls[0] if urls else ""
                if not source_url: error = "EXTERNAL_URL_NOT_FOUND"
            except requests.RequestException as exc:
                error = f"{type(exc).__name__}: {exc}"
        row["source_url"] = source_url
        row["discovery_status"] = "DISCOVERED" if source_url else (
            "NON_COMMON_SHARE" if not row["common_share"] else "FAILED")
        row["error"] = error
        rows.append(row)
    output = pd.DataFrame(rows)
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target, index=False, encoding="utf-8-sig")
    audit = pd.DataFrame(month_audits)
    ap = Path(audit_csv); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    discovered = int((output.get("discovery_status", pd.Series(dtype=str)) == "DISCOVERED").sum())
    return {"target_codes": len(names), "matched_notices": len(output),
            "discovered_common_notices": discovered, "output_csv": str(target), "audit_csv": str(ap)}
