from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def consolidate_historical_legal_chains_v321(
    *, validation_csv: str, chain_csv: str, group_output_csv: str,
    evidence_output_csv: str, audit_output_csv: str, summary_json: str,
) -> dict:
    validation = pd.read_csv(validation_csv, dtype=str).fillna("")
    chain = pd.read_csv(chain_csv, dtype=str).fillna("")
    required_validation = {"queue_event_id", "code", "document_role", "mechanic_family",
                           "child_rcept_no", "parent_queue_event_id", "parent_rcept_no",
                           "semantic_validation_status"}
    required_chain = {"queue_event_id", "source_reference_date"}
    if missing := sorted(required_validation - set(validation.columns)):
        raise ValueError("validation CSV missing columns: " + ", ".join(missing))
    if missing := sorted(required_chain - set(chain.columns)):
        raise ValueError("chain CSV missing columns: " + ", ".join(missing))

    confirmed = validation[validation["semantic_validation_status"].eq(
        "SEMANTIC_CHAIN_CONFIRMED_REVIEW_REQUIRED")].copy()
    if not confirmed["queue_event_id"].is_unique:
        raise ValueError("confirmed chain children must have unique queue_event_id values")
    confirmed = confirmed.merge(
        chain[["queue_event_id", "source_reference_date"]].drop_duplicates("queue_event_id"),
        on="queue_event_id", how="left", validate="one_to_one")
    if confirmed["source_reference_date"].eq("").any():
        raise ValueError("confirmed child missing source_reference_date")

    groups: list[dict[str, str | int]] = []
    for parent_id, items in confirmed.groupby("parent_queue_event_id", sort=True):
        mechanics = sorted(set(items["mechanic_family"]) - {""})
        codes = sorted(set(items["code"].astype(str).str.zfill(6)) - {""})
        parent_receipts = sorted(set(items["parent_rcept_no"]) - {""})
        if len(mechanics) != 1 or len(codes) != 1 or len(parent_receipts) != 1:
            raise ValueError(f"legal event group invariant failed for parent {parent_id}")
        mechanics_docs = items[items["document_role"].isin(["AMENDMENT", "ATTACHMENT"])].copy()
        if len(mechanics_docs):
            controlling = mechanics_docs.sort_values(
                ["source_reference_date", "child_rcept_no"]).iloc[-1]["child_rcept_no"]
            control_source = "LATEST_AMENDMENT_OR_ATTACHMENT"
        else:
            controlling = parent_receipts[0]
            control_source = "PRIMARY_DECISION_NO_CONFIRMED_MECHANICS_AMENDMENT"
        groups.append({
            "parent_queue_event_id": parent_id,
            "code": codes[0],
            "mechanic_family": mechanics[0],
            "parent_rcept_no": parent_receipts[0],
            "confirmed_child_count": int(len(items)),
            "amendment_or_attachment_count": int(items["document_role"].isin(["AMENDMENT", "ATTACHMENT"]).sum()),
            "followup_result_count": int(items["document_role"].eq("FOLLOWUP_RESULT").sum()),
            "confirmed_child_queue_event_ids": "|".join(sorted(items["queue_event_id"])),
            "confirmed_child_rcept_nos": "|".join(sorted(items["child_rcept_no"])),
            "controlling_mechanics_rcept_no": controlling,
            "controlling_document_source": control_source,
            "group_status": "PRIMARY_MECHANICS_UNRESOLVED_CONTROLLING_DOCUMENT_PRESERVED",
        })

    evidence = []
    audits = []
    for item in confirmed.itertuples(index=False):
        role_reason = {
            "AMENDMENT": "CONFIRMED_AMENDMENT_CONSOLIDATED_INTO_PRIMARY_LEGAL_EVENT",
            "ATTACHMENT": "CONFIRMED_ATTACHMENT_CONSOLIDATED_INTO_PRIMARY_LEGAL_EVENT",
            "FOLLOWUP_RESULT": "CONFIRMED_RESULT_REPORT_NOT_AN_INDEPENDENT_ADJUSTMENT_EVENT",
        }.get(item.document_role, "CONFIRMED_CHAIN_CHILD_NOT_INDEPENDENT_EVENT")
        evidence.append({
            "queue_event_id": item.queue_event_id,
            "verification_source": "OPENDART_ORIGINAL_DOCUMENT_LEGAL_CHAIN",
            "verification_reference": f"DART:{item.child_rcept_no}|DART:{item.parent_rcept_no}",
            "resolution_note": role_reason,
        })
        audits.append({
            "queue_event_id": item.queue_event_id,
            "parent_queue_event_id": item.parent_queue_event_id,
            "document_role": item.document_role,
            "mechanic_family": item.mechanic_family,
            "child_rcept_no": item.child_rcept_no,
            "parent_rcept_no": item.parent_rcept_no,
            "integration_status": "NOT_APPLICABLE_CHILD_PRIMARY_REMAINS_UNRESOLVED",
        })

    group_columns = ["parent_queue_event_id", "code", "mechanic_family", "parent_rcept_no",
                     "confirmed_child_count", "amendment_or_attachment_count", "followup_result_count",
                     "confirmed_child_queue_event_ids", "confirmed_child_rcept_nos",
                     "controlling_mechanics_rcept_no", "controlling_document_source", "group_status"]
    evidence_columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    outputs = [
        (pd.DataFrame(groups, columns=group_columns), Path(group_output_csv)),
        (pd.DataFrame(evidence, columns=evidence_columns), Path(evidence_output_csv)),
        (pd.DataFrame(audits), Path(audit_output_csv)),
    ]
    for frame, path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    summary = {
        "confirmed_child_rows": int(len(confirmed)),
        "consolidated_legal_event_groups": int(len(groups)),
        "not_applicable_evidence_rows": int(len(evidence)),
        "groups_with_controlling_amendment": int(sum(
            group["controlling_document_source"] == "LATEST_AMENDMENT_OR_ATTACHMENT" for group in groups)),
        "primary_events_resolved": 0,
        "group_output_csv": str(Path(group_output_csv)),
        "evidence_output_csv": str(Path(evidence_output_csv)),
        "audit_output_csv": str(Path(audit_output_csv)),
    }
    path = Path(summary_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(path)}
