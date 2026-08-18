from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _action_hint(description: str) -> str:
    text = str(description or "")
    for label, action in (
        ("무상증자", "BONUS"), ("유상증자", "RIGHTS"), ("감자", "REVERSE_SPLIT"),
        ("회사분할", "SPINOFF"), ("회사합병", "MERGER"),
    ):
        if label in text:
            return action
    return ""


def build_corporate_action_candidate_manifest_v321(
    *, classified_queue_csv: str, official_candidates_csv: str,
    output_csv: str, summary_json: str,
) -> dict:
    queue = pd.read_csv(classified_queue_csv, dtype=str).fillna("")
    candidates = pd.read_csv(official_candidates_csv, dtype=str).fillna("")
    targets = queue[queue["acquisition_priority"].eq("P1_DIRECT_ISSUER_ACTION")].copy()
    targets["code"] = targets["code"].astype(str).str.zfill(6)
    targets["action_type_hint"] = targets["source_description"].map(_action_hint)
    candidates["code"] = candidates["code"].astype(str).str.zfill(6)
    rows = []
    for _, target in targets.iterrows():
        matches = candidates[
            candidates["code"].eq(target["code"])
            & candidates["action_type_hint"].eq(target["action_type_hint"])
        ].copy()
        exact = matches[matches["rcept_no"].str[:8].eq(target["source_reference_date"])]
        selected = exact.iloc[-1] if not exact.empty else (matches.iloc[-1] if len(matches) == 1 else None)
        status = "OFFICIAL_CANDIDATE_AVAILABLE" if selected is not None else "OFFICIAL_CANDIDATE_ACQUISITION_REQUIRED"
        rows.append({
            "queue_event_id": target["queue_event_id"], "code": target["code"],
            "source_reference_date": target["source_reference_date"],
            "source_description": target["source_description"], "action_type_hint": target["action_type_hint"],
            "candidate_rcept_no": selected["rcept_no"] if selected is not None else "",
            "candidate_event_kind": selected["event_kind"] if selected is not None else "",
            "candidate_known_at": selected["official_known_at"] if selected is not None else "",
            "candidate_event_date": selected["official_event_date"] if selected is not None else "",
            "candidate_source": selected["verification_source"] if selected is not None else "",
            "candidate_reference": selected["verification_reference"] if selected is not None else "",
            "acquisition_status": status,
            "promotion_status": "CANDIDATE_ONLY_NOT_STRICT_EVIDENCE",
        })
    output = pd.DataFrame(rows)
    target_path = Path(output_csv); target_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target_path, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in output["acquisition_status"].value_counts().items()}
    summary = {"phase": "V3.2.1 Phase 5.44", "target_rows": len(output),
               "status_counts": counts, "auto_promoted_rows": 0, "fail_closed": True}
    sp = Path(summary_json); sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"output_csv": str(target_path), "summary_json": str(sp)}
