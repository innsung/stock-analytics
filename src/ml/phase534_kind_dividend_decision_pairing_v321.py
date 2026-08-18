from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
import requests

from src.ml.phase516_kind_crosscheck_v321 import (
    KIND_VIEWER, _extract_kind_doc_no, _extract_kind_document_url,
    _search_kind_disclosures,
)


def _kind_acpt_from_dart(rcept_no: str) -> str:
    value = re.sub(r"[^0-9]", "", str(rcept_no or ""))
    return value[:8] + "0" + value[9:] if len(value) == 14 else ""


def _pair_decision(notice: pd.Series, decisions: pd.DataFrame) -> pd.Series | None:
    notice_date = re.search(r"/external/(\d{4})/(\d{2})/(\d{2})/", notice["source_url"])
    if not notice_date:
        return None
    cutoff = "".join(notice_date.groups())
    candidates = decisions[
        decisions["code"].eq(str(notice["code"]).zfill(6))
        & decisions["known_at"].le(cutoff)
        & decisions["report_nm"].str.contains("현금ㆍ현물배당결정", regex=False)
        & ~decisions["report_nm"].str.contains("자회사", regex=False)
    ].sort_values(["known_at", "rcept_no"], ascending=[False, False])
    return candidates.iloc[0] if not candidates.empty else None


def acquire_paired_kind_dividend_decisions_v321(
    *, notices_csv: str, decision_disclosures_csv: str, documents_dir: str,
    output_csv: str, timeout: int = 20,
) -> dict:
    notices = pd.read_csv(notices_csv, dtype=str).fillna("")
    decisions = pd.read_csv(decision_disclosures_csv, dtype=str).fillna("")
    notices = notices[notices["discovery_status"].eq("DISCOVERED")].copy()
    decisions["code"] = decisions["code"].astype(str).str.zfill(6)
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    session = requests.Session(); session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows = []
    for _, notice in notices.iterrows():
        decision = _pair_decision(notice, decisions)
        status, error, document_url, doc_no, document_path = "NO_DECISION_MATCH", "", "", "", ""
        dart_rcept, kind_acpt, decision_known_at, report_nm = "", "", "", ""
        if decision is not None:
            dart_rcept = decision["rcept_no"]
            kind_acpt = _kind_acpt_from_dart(dart_rcept)
            decision_known_at = decision["known_at"]
            report_nm = decision["report_nm"]
            try:
                search = _search_kind_disclosures(
                    session, code=notice["code"], disclosure_date=decision_known_at, timeout=timeout)
                exact = next((x for x in search if x["kind_acpt_no"] == kind_acpt), None)
                if not exact:
                    raise LookupError("KIND decision receipt not found")
                viewer = KIND_VIEWER.format(rcept_no=kind_acpt)
                response = session.get(viewer, timeout=timeout); response.raise_for_status()
                doc_no = _extract_kind_doc_no(response.text)
                if not doc_no:
                    raise LookupError("KIND decision docNo not found")
                contents = session.get(
                    "https://kind.krx.co.kr/common/disclsviewer.do",
                    params={"method": "searchContents", "docNo": doc_no},
                    headers={"Referer": viewer}, timeout=timeout,
                ); contents.raise_for_status()
                document_url = _extract_kind_document_url(contents.text)
                if not document_url:
                    raise LookupError("KIND external decision URL not found")
                document = session.get(document_url, timeout=timeout); document.raise_for_status()
                if (document.encoding or "").lower() == "iso-8859-1" and document.apparent_encoding:
                    document.encoding = document.apparent_encoding
                path = root / f"{kind_acpt}_{doc_no}.html"
                path.write_text(document.text, encoding="utf-8")
                document_path = str(path)
                status = "ACQUIRED"
            except Exception as exc:
                status, error = "FAILED", f"{type(exc).__name__}: {exc}"
        rows.append({
            "code": str(notice["code"]).zfill(6), "company_name": notice["company_name"],
            "market_notice_url": notice["source_url"], "market_kind_acpt_no": notice["kind_acpt_no"],
            "market_membership_reference": notice.get("attachment_url", ""),
            "dart_rcept_no": dart_rcept, "decision_kind_acpt_no": kind_acpt,
            "decision_kind_doc_no": doc_no, "decision_known_at": decision_known_at,
            "decision_report_nm": report_nm, "decision_document_url": document_url,
            "decision_document_path": document_path, "status": status, "error": error,
        })
    output = pd.DataFrame(rows)
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target, index=False, encoding="utf-8-sig")
    return {"notice_rows": len(notices), "acquired_documents": int((output["status"] == "ACQUIRED").sum()),
            "status_counts": output["status"].value_counts().to_dict(), "output_csv": str(target),
            "documents_dir": str(root)}
