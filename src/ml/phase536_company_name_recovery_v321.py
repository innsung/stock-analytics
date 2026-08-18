from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def recover_acquisition_company_names_v321(
    *, acquisition_manifest_csv: str, dividend_facts_csv: str,
    output_csv: str, audit_csv: str,
) -> dict:
    manifest = pd.read_csv(acquisition_manifest_csv, dtype=str).fillna("")
    facts = pd.read_csv(dividend_facts_csv, dtype=str).fillna("")
    required_m = {"code", "flr_nm", "acquisition_status"}
    required_f = {"code", "raw_json"}
    if required_m - set(manifest.columns):
        raise ValueError("manifest missing columns: " + ", ".join(sorted(required_m - set(manifest.columns))))
    if required_f - set(facts.columns):
        raise ValueError("dividend facts missing columns: " + ", ".join(sorted(required_f - set(facts.columns))))

    names: dict[str, str] = {}
    for _, row in facts.iterrows():
        code = str(row["code"]).zfill(6)
        if code in names:
            continue
        try:
            value = str(json.loads(row["raw_json"]).get("corp_name", "")).strip()
        except (json.JSONDecodeError, TypeError):
            value = ""
        if value:
            names[code] = value

    rows, audits = [], []
    for _, row in manifest.iterrows():
        item = row.to_dict(); code = str(row["code"]).zfill(6)
        before = row["acquisition_status"]
        recovered = ""
        if before == "NEEDS_COMPANY_DISCLOSURE_DISCOVERY" and not row["flr_nm"]:
            recovered = names.get(code, "")
            if recovered:
                item["flr_nm"] = recovered
                item["acquisition_status"] = "READY_FOR_KIND_MARKET_SEARCH"
        rows.append(item)
        audits.append({"code": code, "status_before": before,
                       "status_after": item["acquisition_status"], "recovered_company_name": recovered})
    output, audit = pd.DataFrame(rows), pd.DataFrame(audits)
    op, ap = Path(output_csv), Path(audit_csv); op.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(op, index=False, encoding="utf-8-sig"); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    recovered_count = int(audit["recovered_company_name"].ne("").sum())
    return {"input_rows": len(manifest), "recovered_names": recovered_count,
            "remaining_missing": int((output["acquisition_status"] == "NEEDS_COMPANY_DISCLOSURE_DISCOVERY").sum()),
            "output_csv": str(op), "audit_csv": str(ap)}
