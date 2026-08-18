from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _family(description: str) -> str:
    text = _norm(description)
    if "유상증자" in text:
        return "RIGHTS_OFFERING"
    if "감자" in text:
        return "CAPITAL_REDUCTION"
    if "회사분할" in text or "합병등" in text:
        return "RESTRUCTURING"
    return "OTHER"


def build_direct_action_document_inventory_v321(
    dart_client, *, priority_queue_csv: str, disclosures_csv: str,
    prior_acquisition_csv: str, documents_dir: str, output_csv: str,
) -> dict:
    queue = pd.read_csv(priority_queue_csv, dtype=str).fillna("")
    targets = queue[queue["workstream"].eq("P2_RECENT_DIRECT_ACTION_REVIEW")].copy()
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    disclosures["code"] = disclosures["code"].astype(str).str.zfill(6)
    disclosures["_norm"] = disclosures["report_nm"].map(_norm)
    prior = pd.read_csv(prior_acquisition_csv, dtype=str).fillna("")
    prior = prior[prior["status"].eq("ACQUIRED")].drop_duplicates("queue_event_id").set_index("queue_event_id")
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    rows = []
    for target in targets.itertuples(index=False):
        family = _family(target.source_description)
        group_id = f"{str(target.code).zfill(6)}:{family}"
        status, receipt, paths, source, error = "", "", [], "", ""
        if target.queue_event_id in prior.index:
            old = prior.loc[target.queue_event_id]
            receipt = old["rcept_no"]
            paths = [p for p in old["document_paths"].split("|") if p]
            status, source = "REUSED", "PHASE546"
        else:
            matches = disclosures[
                disclosures["code"].eq(str(target.code).zfill(6))
                & disclosures["rcept_dt"].eq(target.source_reference_date)
                & disclosures["_norm"].eq(_norm(target.source_description))]
            if len(matches) == 1:
                receipt = matches.iloc[0]["rcept_no"]
                try:
                    for index, part in enumerate(dart_client.document_texts(receipt)):
                        safe = re.sub(r"[^A-Za-z0-9._-]", "_", part["name"])
                        path = root / f"{receipt}_{index:02d}_{safe}"
                        path.write_text(part["text"], encoding="utf-8")
                        paths.append(str(path))
                    status, source = ("ACQUIRED", "PHASE561") if paths else ("EMPTY_DOCUMENT", "PHASE561")
                except Exception as exc:
                    status, error = "FAILED", f"{type(exc).__name__}: {exc}"
            else:
                status = "DISCLOSURE_NOT_UNIQUE"
                error = "|".join(matches["rcept_no"].tolist())
        rows.append({"queue_event_id": target.queue_event_id, "code": str(target.code).zfill(6),
            "source_reference_date": target.source_reference_date,
            "source_description": target.source_description, "action_family": family,
            "candidate_legal_event_group": group_id, "rcept_no": receipt,
            "document_status": status, "document_source": source,
            "document_paths": "|".join(paths), "error": error,
            "promotion_status": "DOCUMENT_INVENTORY_ONLY_NOT_PROMOTED"})
    output = pd.DataFrame(rows)
    initially_usable = output["document_status"].isin(["REUSED", "ACQUIRED"])
    covered_groups = set(output.loc[initially_usable, "candidate_legal_event_group"])
    covered_no_file = (
        output["document_status"].eq("FAILED")
        & output["error"].str.contains("status>014|status&gt;014|status=014|<status>014", regex=True)
        & output["candidate_legal_event_group"].isin(covered_groups)
    )
    output.loc[covered_no_file, "document_status"] = "GROUP_COVERED_NO_STANDALONE_FILE"
    output.loc[covered_no_file, "document_source"] = "SAME_LEGAL_EVENT_GROUP"
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(path, index=False, encoding="utf-8-sig")
    usable = output["document_status"].isin(["REUSED", "ACQUIRED", "GROUP_COVERED_NO_STANDALONE_FILE"])
    return {"target_rows": len(output), "reused_rows": int(output["document_status"].eq("REUSED").sum()),
            "acquired_rows": int(output["document_status"].eq("ACQUIRED").sum()),
            "group_covered_rows": int(output["document_status"].eq("GROUP_COVERED_NO_STANDALONE_FILE").sum()),
            "usable_rows": int(usable.sum()),
            "candidate_legal_event_groups": int(output.loc[usable, "candidate_legal_event_group"].nunique()),
            "output_csv": str(path), "documents_dir": str(root)}
