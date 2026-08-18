from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


def extract_kind_aggregate_market_targets_v321(
    *, aggregate_manifest_csv: str, acquisition_manifest_csv: str,
    output_csv: str, audit_csv: str, timeout: int = 20,
) -> dict:
    sources = pd.read_csv(aggregate_manifest_csv, dtype=str).fillna("")
    acquisition = pd.read_csv(acquisition_manifest_csv, dtype=str).fillna("")
    required_s = {"market_name", "kind_acpt_no", "kind_doc_no", "source_url"}
    required_a = {"code", "flr_nm", "acquisition_status"}
    if required_s - set(sources.columns):
        raise ValueError("aggregate manifest missing columns: " + ", ".join(sorted(required_s - set(sources.columns))))
    if required_a - set(acquisition.columns):
        raise ValueError("acquisition manifest missing columns: " + ", ".join(sorted(required_a - set(acquisition.columns))))
    targets = acquisition[acquisition["acquisition_status"].eq("READY_FOR_KIND_MARKET_SEARCH")]
    rows, audits = [], []
    for _, source in sources.iterrows():
        status, error, text, http_status = "FAILED", "", "", ""
        try:
            response = requests.get(source["source_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
            http_status = str(response.status_code); response.raise_for_status()
            if (response.encoding or "").lower() == "iso-8859-1" and response.apparent_encoding:
                response.encoding = response.apparent_encoding
            text = " ".join(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True).split())
            status = "SUCCESS"
        except requests.RequestException as exc:
            error = f"{type(exc).__name__}: {exc}"
        matches = 0
        if status == "SUCCESS":
            for _, target in targets.iterrows():
                name = target["flr_nm"].strip()
                if name and name in text:
                    matches += 1
                    rows.append({
                        "code": str(target["code"]).zfill(6), "company_name": name,
                        "notice_title": f"Aggregate dividend ex-date notice ({source['market_name']})",
                        "kind_acpt_no": source["kind_acpt_no"], "kind_doc_no": source["kind_doc_no"],
                        "common_share": True, "search_window_start": "2026-03-27",
                        "search_window_end": "2026-03-27", "source_url": source["source_url"],
                        "discovery_status": "DISCOVERED", "error": "",
                    })
        audits.append({"market_name": source["market_name"], "source_url": source["source_url"],
                       "status": status, "http_status": http_status, "matched_targets": matches, "error": error})
    output, audit = pd.DataFrame(rows), pd.DataFrame(audits)
    op, ap = Path(output_csv), Path(audit_csv); op.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(op, index=False, encoding="utf-8-sig"); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    return {"source_rows": len(sources), "matched_targets": len(output),
            "matched_codes": sorted(output["code"].unique().tolist()) if not output.empty else [],
            "output_csv": str(op), "audit_csv": str(ap)}
