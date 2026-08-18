from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def acquire_subsidiary_action_documents_v321(
    dart_client, *, priority_queue_csv: str, disclosures_csv: str,
    documents_dir: str, output_csv: str,
) -> dict:
    queue = pd.read_csv(priority_queue_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    targets = queue[queue["workstream"].eq("P1_SUBSIDIARY_APPLICABILITY_REVIEW")].copy()
    disclosures["code"] = disclosures["code"].astype(str).str.zfill(6)
    disclosures["_norm_report"] = disclosures["report_nm"].map(_norm)
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    rows = []
    for target in targets.itertuples(index=False):
        matches = disclosures[
            disclosures["code"].eq(str(target.code).zfill(6))
            & disclosures["rcept_dt"].eq(target.source_reference_date)
            & disclosures["_norm_report"].eq(_norm(target.source_description))
        ]
        status, rcept_no, paths, error = "DISCLOSURE_NOT_FOUND", "", [], ""
        if len(matches) == 1:
            rcept_no = matches.iloc[0]["rcept_no"]
            try:
                parts = dart_client.document_texts(rcept_no)
                for index, part in enumerate(parts):
                    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(part["name"]))
                    path = root / f"{rcept_no}_{index:02d}_{safe}"
                    path.write_text(part["text"], encoding="utf-8")
                    paths.append(str(path))
                status = "ACQUIRED" if paths else "EMPTY_DOCUMENT"
            except Exception as exc:
                status, error = "FAILED", f"{type(exc).__name__}: {exc}"
        elif len(matches) > 1:
            status = "AMBIGUOUS_DISCLOSURES"
            error = "|".join(matches["rcept_no"].tolist())
        rows.append({
            "queue_event_id": target.queue_event_id, "code": str(target.code).zfill(6),
            "source_reference_date": target.source_reference_date,
            "source_description": target.source_description, "match_count": len(matches),
            "rcept_no": rcept_no, "document_parts": len(paths),
            "document_paths": "|".join(paths), "status": status, "error": error,
            "promotion_status": "OFFICIAL_DOCUMENT_ACQUIRED_NOT_TERMINAL_EVIDENCE" if status == "ACQUIRED" else "NOT_PROMOTED",
        })
    output = pd.DataFrame(rows)
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(path, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in output["status"].value_counts().items()}
    return {"target_rows": len(output), "acquired_rows": counts.get("ACQUIRED", 0),
            "ambiguous_rows": counts.get("AMBIGUOUS_DISCLOSURES", 0),
            "status_counts": counts, "output_csv": str(path), "documents_dir": str(root)}
