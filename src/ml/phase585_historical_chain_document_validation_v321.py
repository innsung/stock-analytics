from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


MECHANIC_TERMS = {
    "RIGHTS_OFFERING": ("유상증자",),
    "BONUS_ISSUE": ("무상증자",),
    "CAPITAL_REDUCTION": ("감자",),
    "MERGER": ("합병",),
    "SPINOFF_OR_SPLIT_MERGER": ("분할",),
    "SHARE_EXCHANGE_OR_TRANSFER": ("주식교환", "주식이전"),
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _plain(parts: list[dict[str, str]]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def _contains_mechanic(text: str, mechanic: str) -> bool:
    return any(term in text for term in MECHANIC_TERMS.get(mechanic, ()))


def _save_or_load(dart_client, receipt: str, root: Path) -> tuple[list[dict[str, str]], str, str]:
    existing = sorted(root.glob(f"{receipt}_*"))
    if existing:
        try:
            return ([{"name": path.name, "text": path.read_text(encoding="utf-8")} for path in existing],
                    "REUSED", "")
        except (OSError, UnicodeError):
            pass
    try:
        parts = dart_client.document_texts(receipt)
        paths = []
        for index, part in enumerate(parts):
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(part.get("name", "document.xml")))
            path = root / f"{receipt}_{index:02d}_{safe}"
            path.write_text(str(part.get("text", "")), encoding="utf-8")
            paths.append(path)
        return parts, "ACQUIRED" if parts else "EMPTY_DOCUMENT", ""
    except Exception as exc:
        return [], "FAILED", f"{type(exc).__name__}: {exc}"


def validate_historical_chain_documents_v321(
    dart_client, *, chain_csv: str, execution_manifest_csv: str,
    disclosures_csv: str, documents_dir: str, output_csv: str,
    review_queue_csv: str, summary_json: str,
) -> dict:
    chain = pd.read_csv(chain_csv, dtype=str).fillna("")
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    targets = chain[chain["chain_status"].eq("READY_FOR_ORIGINAL_DOCUMENT_SEMANTIC_VALIDATION")].copy()
    manifest["code"] = manifest["code"].astype(str).str.zfill(6)
    disclosures["code"] = disclosures["code"].astype(str).str.zfill(6)
    disclosures["_norm_title"] = disclosures["report_nm"].map(_norm)
    disclosures = disclosures.drop_duplicates(["code", "rcept_dt", "_norm_title", "rcept_no"])
    by_id = manifest.drop_duplicates("queue_event_id").set_index("queue_event_id")
    root = Path(documents_dir)
    root.mkdir(parents=True, exist_ok=True)
    cache: dict[str, tuple[list[dict[str, str]], str, str]] = {}

    def document(receipt: str) -> tuple[list[dict[str, str]], str, str]:
        if receipt not in cache:
            cache[receipt] = _save_or_load(dart_client, receipt, root)
        return cache[receipt]

    rows: list[dict[str, str | bool]] = []
    reviews: list[dict[str, str | bool]] = []
    for target in targets.itertuples(index=False):
        parent_id = str(target.candidate_parent_queue_event_ids)
        parent = by_id.loc[parent_id] if parent_id in by_id.index else None
        parent_receipt = ""
        if parent is not None:
            matches = disclosures[
                disclosures["code"].eq(str(parent["code"]).zfill(6))
                & disclosures["rcept_dt"].eq(str(parent["source_reference_date"]))
                & disclosures["_norm_title"].eq(_norm(parent["source_description"]))
            ]
            receipts = sorted(set(matches["rcept_no"]) - {""})
            parent_receipt = receipts[0] if len(receipts) == 1 else ""
        child_parts, child_status, child_error = document(target.child_rcept_no)
        parent_parts, parent_status, parent_error = document(parent_receipt) if parent_receipt else ([], "NOT_UNIQUE", "")
        child_text, parent_text = _plain(child_parts), _plain(parent_parts)
        child_mechanic = _contains_mechanic(child_text, target.mechanic_family)
        parent_mechanic = _contains_mechanic(parent_text, target.mechanic_family)
        if target.document_role == "AMENDMENT":
            role_semantics = "정정" in child_text
        elif target.document_role == "ATTACHMENT":
            role_semantics = "첨부" in _norm(target.source_description)
        else:
            role_semantics = any(term in child_text for term in ("종료보고서", "발행결과", "청약결과", "합병완료"))
        semantic_valid = bool(child_mechanic and parent_mechanic and role_semantics)
        status = (
            "SEMANTIC_CHAIN_CONFIRMED_REVIEW_REQUIRED" if semantic_valid
            else "DOCUMENT_ACQUIRED_SEMANTIC_LINK_INCOMPLETE"
            if child_status in {"ACQUIRED", "REUSED"} and parent_status in {"ACQUIRED", "REUSED"}
            else "DOCUMENT_ACQUISITION_INCOMPLETE"
        )
        row = {
            "queue_event_id": target.queue_event_id,
            "code": str(target.code).zfill(6),
            "document_role": target.document_role,
            "mechanic_family": target.mechanic_family,
            "child_rcept_no": target.child_rcept_no,
            "parent_queue_event_id": parent_id,
            "parent_rcept_no": parent_receipt,
            "child_document_status": child_status,
            "parent_document_status": parent_status,
            "child_mechanic_confirmed": child_mechanic,
            "parent_mechanic_confirmed": parent_mechanic,
            "role_semantics_confirmed": role_semantics,
            "semantic_validation_status": status,
            "error": "|".join(value for value in (child_error, parent_error) if value),
            "promotion_status": "NOT_PROMOTED_PRIMARY_MECHANICS_STILL_UNRESOLVED",
        }
        rows.append(row)
        if not semantic_valid:
            reviews.append(row)

    columns = ["queue_event_id", "code", "document_role", "mechanic_family", "child_rcept_no",
               "parent_queue_event_id", "parent_rcept_no", "child_document_status", "parent_document_status",
               "child_mechanic_confirmed", "parent_mechanic_confirmed", "role_semantics_confirmed",
               "semantic_validation_status", "error", "promotion_status"]
    output, review = pd.DataFrame(rows, columns=columns), pd.DataFrame(reviews, columns=columns)
    output_path, review_path = Path(output_csv), Path(review_queue_csv)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")
    review.to_csv(review_path, index=False, encoding="utf-8-sig")
    summary = {
        "target_rows": int(len(targets)),
        "unique_receipts_processed": int(len(cache)),
        "semantic_chains_confirmed": int(output["semantic_validation_status"].eq(
            "SEMANTIC_CHAIN_CONFIRMED_REVIEW_REQUIRED").sum()),
        "semantic_or_acquisition_review_rows": int(len(review)),
        "resolution_status_changed": False,
        "documents_dir": str(root),
        "output_csv": str(output_path),
        "review_queue_csv": str(review_path),
    }
    path = Path(summary_json)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(path)}
