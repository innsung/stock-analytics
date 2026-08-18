from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


PREFIX = re.compile(r"^(?:\[[^\]]*(?:정정|첨부|추가)[^\]]*\])+", re.IGNORECASE)


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _base_title(value: str) -> str:
    return PREFIX.sub("", _norm(value))


def _days(value: str) -> pd.Timestamp:
    return pd.to_datetime(str(value), format="%Y%m%d", errors="coerce")


def build_historical_legal_event_chain_v321(
    *, execution_manifest_csv: str, disclosures_csv: str,
    output_csv: str, review_queue_csv: str, summary_json: str,
) -> dict:
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    required_manifest = {"queue_event_id", "code", "source_reference_date", "source_description",
                         "document_role", "mechanic_family", "execution_lane"}
    required_disclosures = {"code", "rcept_dt", "report_nm", "rcept_no"}
    if missing := sorted(required_manifest - set(manifest.columns)):
        raise ValueError("execution manifest missing columns: " + ", ".join(missing))
    if missing := sorted(required_disclosures - set(disclosures.columns)):
        raise ValueError("disclosures missing columns: " + ", ".join(missing))

    manifest["code"] = manifest["code"].astype(str).str.zfill(6)
    disclosures["code"] = disclosures["code"].astype(str).str.zfill(6)
    disclosures["_norm_title"] = disclosures["report_nm"].map(_norm)
    disclosures = disclosures.sort_values("rcept_no").drop_duplicates("rcept_no", keep="last")
    targets = manifest[manifest["execution_lane"].eq("CORPORATE_ACTION_LEGAL_EVENT_CHAIN")].copy()
    primaries = manifest[manifest["document_role"].eq("PRIMARY_OR_AMENDED_DECISION")].copy()
    primaries["_base_title"] = primaries["source_description"].map(_base_title)

    rows: list[dict[str, str | int]] = []
    review_rows: list[dict[str, str]] = []
    for target in targets.itertuples(index=False):
        exact = disclosures[
            disclosures["code"].eq(target.code)
            & disclosures["rcept_dt"].eq(str(target.source_reference_date))
            & disclosures["_norm_title"].eq(_norm(target.source_description))
        ]
        child_receipts = sorted(set(exact["rcept_no"]) - {""})
        child_receipt = child_receipts[0] if len(child_receipts) == 1 else ""
        child_date = _days(target.source_reference_date)
        candidates = primaries[
            primaries["code"].eq(target.code)
            & primaries["mechanic_family"].eq(target.mechanic_family)
        ].copy()
        candidates["_date"] = pd.to_datetime(
            candidates["source_reference_date"], format="%Y%m%d", errors="coerce"
        )
        candidates = candidates[
            candidates["_date"].notna()
            & (candidates["_date"] <= child_date)
            & ((child_date - candidates["_date"]).dt.days <= 730)
        ]
        target_base = _base_title(target.source_description)
        title_matches = candidates[candidates["_base_title"].eq(target_base)]
        selection_basis = "NORMALIZED_TITLE_AND_MECHANIC" if len(title_matches) else "MECHANIC_AND_NEAREST_PRIOR_DATE"
        pool = title_matches if len(title_matches) else candidates
        if len(pool):
            nearest_date = pool["source_reference_date"].max()
            nearest = pool[pool["source_reference_date"].eq(nearest_date)]
        else:
            nearest = pool
        parent_ids = sorted(set(nearest["queue_event_id"]))
        parent_status = (
            "UNIQUE_PARENT_CANDIDATE" if len(parent_ids) == 1
            else "AMBIGUOUS_PARENT_CANDIDATES" if len(parent_ids) > 1
            else "NO_PARENT_CANDIDATE"
        )
        receipt_status = (
            "UNIQUE_CHILD_RECEIPT" if len(child_receipts) == 1
            else "AMBIGUOUS_CHILD_RECEIPTS" if len(child_receipts) > 1
            else "CHILD_RECEIPT_NOT_FOUND"
        )
        chain_status = (
            "READY_FOR_ORIGINAL_DOCUMENT_SEMANTIC_VALIDATION"
            if receipt_status == "UNIQUE_CHILD_RECEIPT" and parent_status == "UNIQUE_PARENT_CANDIDATE"
            else "MANUAL_PARENT_OR_RECEIPT_REVIEW_REQUIRED"
        )
        row = {
            "queue_event_id": target.queue_event_id,
            "code": target.code,
            "source_reference_date": target.source_reference_date,
            "source_description": target.source_description,
            "document_role": target.document_role,
            "mechanic_family": target.mechanic_family,
            "child_rcept_no": child_receipt,
            "child_receipt_status": receipt_status,
            "candidate_parent_count": int(len(parent_ids)),
            "candidate_parent_queue_event_ids": "|".join(parent_ids),
            "parent_selection_basis": selection_basis,
            "parent_candidate_status": parent_status,
            "chain_status": chain_status,
            "promotion_status": "NOT_PROMOTED_REQUIRES_ORIGINAL_DOCUMENT_SEMANTICS",
        }
        rows.append(row)
        if chain_status != "READY_FOR_ORIGINAL_DOCUMENT_SEMANTIC_VALIDATION":
            review_rows.append(row)

    columns = ["queue_event_id", "code", "source_reference_date", "source_description",
               "document_role", "mechanic_family", "child_rcept_no", "child_receipt_status",
               "candidate_parent_count", "candidate_parent_queue_event_ids", "parent_selection_basis",
               "parent_candidate_status", "chain_status", "promotion_status"]
    output = pd.DataFrame(rows, columns=columns)
    review = pd.DataFrame(review_rows, columns=columns)
    output_path, review_path = Path(output_csv), Path(review_queue_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")
    review.to_csv(review_path, index=False, encoding="utf-8-sig")
    summary = {
        "target_rows": int(len(targets)),
        "unique_child_receipts": int(output["child_receipt_status"].eq("UNIQUE_CHILD_RECEIPT").sum()),
        "unique_parent_candidates": int(output["parent_candidate_status"].eq("UNIQUE_PARENT_CANDIDATE").sum()),
        "ready_for_semantic_validation": int(output["chain_status"].eq(
            "READY_FOR_ORIGINAL_DOCUMENT_SEMANTIC_VALIDATION").sum()),
        "manual_review_rows": int(len(review)),
        "resolution_status_changed": False,
        "output_csv": str(output_path),
        "review_queue_csv": str(review_path),
    }
    path = Path(summary_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(path)}
