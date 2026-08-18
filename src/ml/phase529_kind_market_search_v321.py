from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup


MAIN_URL = "https://kind.krx.co.kr/disclosure/searchtotalinfo.do?method=searchTotalInfoMain"
SEARCH_URL = "https://kind.krx.co.kr/disclosure/searchtotalinfo.do"
VIEWER_URL = "https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={}"
CONTENTS_URL = "https://kind.krx.co.kr/common/disclsviewer.do?method=searchContents&docNo={}"
EXTERNAL_RE = re.compile(r"https://kind\.krx\.co\.kr/external/[^'\"]+")


def discover_kind_market_exdate_notices_v321(
    *, candidates_csv: str, output_csv: str, audit_csv: str, timeout: int = 20
) -> dict:
    candidates = pd.read_csv(candidates_csv, dtype=str).fillna("")
    required = {"code", "company_name", "expected_record_date"}
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError("candidates missing columns: " + ", ".join(sorted(missing)))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    session.get(MAIN_URL, timeout=timeout).raise_for_status()
    found, audits = [], []
    for _, row in candidates.iterrows():
        record = datetime.strptime(row["expected_record_date"], "%Y%m%d")
        start, end = record - timedelta(days=14), record + timedelta(days=3)
        response = session.post(
            SEARCH_URL,
            data={
                "method": "searchTotalInfoSub", "forward": "searchtotalinfo_detail",
                "fdName": "all_mktact_idx", "pageIndex": "1", "currentPageSize": "100",
                "scn": "mktact", "srchFd": "2", "kwd": "배당락 기준 가격 안내",
                "fromData": start.strftime("%Y-%m-%d"), "toData": end.strftime("%Y-%m-%d"),
            },
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": MAIN_URL},
            timeout=timeout,
        )
        response.raise_for_status()
        if (response.encoding or "").lower() == "iso-8859-1" and response.apparent_encoding:
            response.encoding = response.apparent_encoding
        matches = []
        for item in BeautifulSoup(response.text, "html.parser").select("dt.img"):
            name, link = item.select_one("strong.name"), item.select_one("span.subject a")
            if not name or not link or row["company_name"] not in name.get_text(" ", strip=True):
                continue
            title = " ".join(link.get_text(" ", strip=True).split())
            ids = re.findall(r"\d{14}", link.get("onclick", ""))
            if "배당락" in title and len(ids) >= 2:
                matches.append((title, ids[0], ids[1]))

        # A company can have separate preferred-share notices. The title without
        # a share-class suffix is the common-share notice.
        common = [m for m in matches if m[0].rstrip().endswith("안내")]
        selected = common[0] if len(common) == 1 else None
        source_url = ""
        if selected:
            _, acpt_no, doc_no = selected
            viewer = VIEWER_URL.format(acpt_no)
            session.get(viewer, timeout=timeout).raise_for_status()
            contents = session.get(CONTENTS_URL.format(doc_no), headers={"Referer": viewer}, timeout=timeout)
            contents.raise_for_status()
            urls = EXTERNAL_RE.findall(contents.text)
            source_url = urls[0] if urls else ""
            if source_url:
                found.append({
                    "code": str(row["code"]).zfill(6), "company_name": row["company_name"],
                    "source_url": source_url, "expected_record_date": row["expected_record_date"],
                    "kind_acpt_no": acpt_no, "kind_doc_no": doc_no,
                })
        audits.append({
            "code": str(row["code"]).zfill(6), "company_name": row["company_name"],
            "expected_record_date": row["expected_record_date"], "matched_notices": len(matches),
            "status": "DISCOVERED" if source_url else ("AMBIGUOUS" if matches else "NO_INDIVIDUAL_NOTICE"),
            "source_url": source_url,
        })

    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(found).to_csv(output_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(audit_csv, index=False, encoding="utf-8-sig")
    return {"candidate_rows": len(candidates), "discovered_rows": len(found),
            "status_counts": pd.DataFrame(audits)["status"].value_counts().to_dict()}
