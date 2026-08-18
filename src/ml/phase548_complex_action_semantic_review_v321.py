from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def review_complex_corporate_actions_v321(
    *, candidate_manifest_csv: str, official_candidates_csv: str,
    not_applicable_csv: str, audit_csv: str,
) -> dict:
    manifest = pd.read_csv(candidate_manifest_csv, dtype=str).fillna("")
    official = pd.read_csv(official_candidates_csv, dtype=str).fillna("")
    official = official.drop_duplicates("rcept_no").set_index("rcept_no")
    na_rows, audits = [], []
    available = manifest[manifest["acquisition_status"].eq("OFFICIAL_CANDIDATE_AVAILABLE")]
    available = available[available["action_type_hint"].isin(["MERGER", "SPINOFF"])]
    for _, row in available.iterrows():
        receipt = row["candidate_rcept_no"]
        candidate = official.loc[receipt] if receipt in official.index else None
        status, reason = "REQUIRES_COMPLEX_ACTION_RESOLUTION", ""
        if candidate is not None:
            raw = json.loads(candidate["raw_json"])
            action = row["action_type_hint"]
            if action == "MERGER":
                ratio = str(raw.get("mg_rt", ""))
                new_common = str(raw.get("mgnstk_cstk_cnt", ""))
                new_preferred = str(raw.get("mgnstk_ostk_cnt", ""))
                no_new_shares = ("무증자합병" in ratio or "0.000000" in ratio) and new_common in {"", "-", "0"} and new_preferred in {"", "-", "0"}
                if no_new_shares:
                    status = "EXPLICIT_NOT_APPLICABLE"
                    reason = "WHOLLY_OWNED_1_TO_0_MERGER_WITH_NO_NEW_SHARES"
                    na_rows.append({
                        "queue_event_id": row["queue_event_id"],
                        "verification_source": candidate["verification_source"],
                        "verification_reference": candidate["verification_reference"],
                        "resolution_note": reason,
                    })
            elif action == "SPINOFF":
                listed = str(raw.get("dvfcmp_rlst_atn", "")) == "예"
                new_ratio = str(raw.get("dv_rt", ""))
                if listed and new_ratio:
                    reason = "LISTED_HUMAN_SPINOFF_REQUIRES_DISTRIBUTED_SECURITY_VALUATION"
        audits.append({
            "queue_event_id": row["queue_event_id"], "code": str(row["code"]).zfill(6),
            "action_type_hint": row["action_type_hint"], "candidate_rcept_no": receipt,
            "semantic_status": status, "reason": reason,
            "promotion_status": "NOT_APPLICABLE_EVIDENCE" if status == "EXPLICIT_NOT_APPLICABLE" else "NOT_PROMOTED",
        })
    na = pd.DataFrame(na_rows, columns=["queue_event_id", "verification_source", "verification_reference", "resolution_note"])
    audit = pd.DataFrame(audits)
    np, ap = Path(not_applicable_csv), Path(audit_csv); np.parent.mkdir(parents=True, exist_ok=True)
    na.to_csv(np, index=False, encoding="utf-8-sig"); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    return {"reviewed_rows": len(audit), "not_applicable_rows": len(na),
            "complex_rows": int((audit["semantic_status"] == "REQUIRES_COMPLEX_ACTION_RESOLUTION").sum()),
            "not_applicable_csv": str(np), "audit_csv": str(ap)}
