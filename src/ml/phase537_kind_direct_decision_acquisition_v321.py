from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from src.ml.phase516_kind_crosscheck_v321 import KIND_VIEWER, _extract_kind_doc_no, _extract_kind_document_url


def acquire_direct_kind_dividend_decisions_v321(
    *, manifest_csv: str, documents_dir: str, output_csv: str, timeout: int = 20,
) -> dict:
    manifest = pd.read_csv(manifest_csv, dtype=str).fillna("")
    required = {
        "code", "company_name", "market_notice_url", "market_kind_acpt_no",
        "decision_kind_acpt_no", "decision_known_at",
    }
    missing = required - set(manifest.columns)
    if missing:
        raise ValueError("direct decision manifest missing columns: " + ", ".join(sorted(missing)))
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    session = requests.Session(); session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows = []
    for _, item in manifest.iterrows():
        doc_no = document_url = document_path = error = ""
        status = "FAILED"
        try:
            viewer = KIND_VIEWER.format(rcept_no=item["decision_kind_acpt_no"])
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
            path = root / f"{item['decision_kind_acpt_no']}_{doc_no}.html"
            path.write_text(document.text, encoding="utf-8")
            document_path, status = str(path), "ACQUIRED"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        rows.append({
            "code": str(item["code"]).zfill(6), "company_name": item["company_name"],
            "market_notice_url": item["market_notice_url"],
            "market_kind_acpt_no": item["market_kind_acpt_no"], "dart_rcept_no": "",
            "decision_kind_acpt_no": item["decision_kind_acpt_no"], "decision_kind_doc_no": doc_no,
            "decision_known_at": item["decision_known_at"], "decision_report_nm": "현금ㆍ현물 배당 결정",
            "decision_document_url": document_url, "decision_document_path": document_path,
            "status": status, "error": error,
        })
    output = pd.DataFrame(rows)
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target, index=False, encoding="utf-8-sig")
    return {"manifest_rows": len(manifest), "acquired_documents": int((output["status"] == "ACQUIRED").sum()),
            "status_counts": output["status"].value_counts().to_dict(), "output_csv": str(target),
            "documents_dir": str(root)}
