from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def _segments(start: str, end: str) -> list[tuple[str, str]]:
    first, last = int(start[:4]), int(end[:4])
    return [(max(start, f"{year}0101"), min(end, f"{year}1231"))
            for year in range(first, last + 1)]


def acquire_historical_dividend_decisions_v321(
    dart_client, *, inventory_csv: str, documents_dir: str, output_csv: str,
) -> dict:
    inventory = pd.read_csv(inventory_csv, dtype=str).fillna("")
    targets = inventory[inventory["inventory_status"].eq("CORRECTED_HISTORICAL_MARKET_SEARCH_REQUIRED")]
    corp_map = dart_client.corp_code_map()
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    rows = []
    for target in targets.itertuples(index=False):
        code = str(target.code).zfill(6)
        corp_code = corp_map.get(code, "")
        disclosures = []
        if corp_code:
            for start, end in _segments(target.corrected_search_start, target.corrected_search_end):
                disclosures.extend(dart_client.disclosure_list(corp_code, start, end, 100))
        unique = {str(item.get("rcept_no", "")): item for item in disclosures if item.get("rcept_no")}
        decisions = []
        for item in unique.values():
            name = re.sub(r"\s+", "", str(item.get("report_nm", "")))
            if "현금ㆍ현물배당결정" in name and "자회사" not in name and "종속회사" not in name:
                decisions.append(item)
        if not decisions:
            rows.append({"queue_event_id": target.queue_event_id, "code": code,
                "corp_code": corp_code, "report_nm": "", "rcept_no": "", "rcept_dt": "",
                "document_paths": "", "acquisition_status": "NO_DIRECT_DIVIDEND_DECISION_FOUND",
                "error": "", "promotion_status": "NOT_PROMOTED_NO_DECISION"})
            continue
        for item in sorted(decisions, key=lambda x: (str(x.get("rcept_dt", "")), str(x.get("rcept_no", "")))):
            receipt, paths, error, status = str(item["rcept_no"]), [], "", ""
            try:
                for index, part in enumerate(dart_client.document_texts(receipt)):
                    safe = re.sub(r"[^A-Za-z0-9._-]", "_", part["name"])
                    path = root / f"{receipt}_{index:02d}_{safe}"
                    path.write_text(part["text"], encoding="utf-8")
                    paths.append(str(path))
                status = "ACQUIRED" if paths else "EMPTY_DOCUMENT"
            except Exception as exc:
                status, error = "FAILED", f"{type(exc).__name__}: {exc}"
            rows.append({"queue_event_id": target.queue_event_id, "code": code,
                "corp_code": corp_code, "report_nm": item.get("report_nm", ""),
                "rcept_no": receipt, "rcept_dt": item.get("rcept_dt", ""),
                "document_paths": "|".join(paths), "acquisition_status": status,
                "error": error, "promotion_status": "OFFICIAL_DECISION_ACQUIRED_NOT_STRICT_EVIDENCE" if status == "ACQUIRED" else "NOT_PROMOTED"})
    output = pd.DataFrame(rows)
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(path, index=False, encoding="utf-8-sig")
    return {"target_queue_rows": len(targets), "manifest_rows": len(output),
            "queue_rows_with_candidates": int(output.loc[output["rcept_no"].ne(""), "queue_event_id"].nunique()),
            "candidate_documents_acquired": int(output["acquisition_status"].eq("ACQUIRED").sum()),
            "queue_rows_without_candidates": int(output.loc[output["rcept_no"].eq(""), "queue_event_id"].nunique()),
            "output_csv": str(path), "documents_dir": str(root)}
