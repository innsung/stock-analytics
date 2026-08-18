from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def acquire_missing_corporate_action_documents_v321(
    dart_client, *, candidate_manifest_csv: str, disclosures_csv: str,
    documents_dir: str, output_csv: str,
) -> dict:
    manifest = pd.read_csv(candidate_manifest_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    targets = manifest[manifest["acquisition_status"].eq("OFFICIAL_CANDIDATE_ACQUISITION_REQUIRED")].copy()
    disclosures["code"] = disclosures["code"].astype(str).str.zfill(6)
    disclosures["_norm_report"] = disclosures["report_nm"].map(_norm)
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, target in targets.iterrows():
        code = str(target["code"]).zfill(6)
        matches = disclosures[
            disclosures["code"].eq(code)
            & disclosures["rcept_dt"].eq(target["source_reference_date"])
            & disclosures["_norm_report"].eq(_norm(target["source_description"]))
        ]
        status, error, rcept_no, part_count, paths = "DISCLOSURE_NOT_FOUND", "", "", 0, []
        if len(matches) == 1:
            rcept_no = matches.iloc[0]["rcept_no"]
            try:
                parts = dart_client.document_texts(rcept_no)
                for index, part in enumerate(parts):
                    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", str(part["name"]))
                    path = root / f"{rcept_no}_{index:02d}_{safe_name}"
                    path.write_text(part["text"], encoding="utf-8")
                    paths.append(str(path))
                part_count, status = len(parts), "ACQUIRED"
            except Exception as exc:
                status, error = "FAILED", f"{type(exc).__name__}: {exc}"
        elif len(matches) > 1:
            status, error = "AMBIGUOUS_DISCLOSURES", f"matches={len(matches)}"
        rows.append({
            "queue_event_id": target["queue_event_id"], "code": code,
            "source_reference_date": target["source_reference_date"],
            "source_description": target["source_description"], "action_type_hint": target["action_type_hint"],
            "rcept_no": rcept_no, "document_parts": part_count,
            "document_paths": "|".join(paths), "status": status, "error": error,
            "promotion_status": "OFFICIAL_DOCUMENT_ACQUIRED_NOT_STRICT_EVIDENCE" if status == "ACQUIRED" else "",
        })
    output = pd.DataFrame(rows)
    target_path = Path(output_csv); target_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target_path, index=False, encoding="utf-8-sig")
    return {"target_rows": len(targets), "acquired_rows": int((output["status"] == "ACQUIRED").sum()),
            "status_counts": output["status"].value_counts().to_dict(), "output_csv": str(target_path),
            "documents_dir": str(root)}
