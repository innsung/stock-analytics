from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd


def _plain(paths: str) -> str:
    text = "\n".join(Path(p).read_text(encoding="utf-8", errors="ignore")
                     for p in str(paths).split("|") if p)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text)


def parse_subsidiary_action_applicability_v321(
    *, acquisition_manifest_csv: str, audit_output_csv: str,
    not_applicable_output_csv: str,
) -> dict:
    manifest = pd.read_csv(acquisition_manifest_csv, dtype=str).fillna("")
    rows, evidence = [], []
    for r in manifest.itertuples(index=False):
        semantic_status, reason, subject_type = "UNRESOLVED", "", ""
        if r.status == "ACQUIRED":
            plain = _plain(r.document_paths)
            subsidiary = re.search(r"종속회사인\s+(.{1,120}?)\s+의\s+주요경영사항\s*신고", plain)
            child = re.search(r"자회사인\s+(.{1,120}?)\s+의\s+주요경영사항\s*신고", plain)
            match = subsidiary or child
            if match:
                subject_type = "SUBSIDIARY" if subsidiary else "CHILD_COMPANY"
                semantic_status = "EXPLICIT_NOT_APPLICABLE_TO_PARENT_SECURITY"
                reason = "ACTION_ISSUER_IS_SEPARATE_SUBSIDIARY_NO_PARENT_SECURITY_MECHANICS"
                evidence.append({
                    "queue_event_id": r.queue_event_id,
                    "verification_source": "OPENDART_ORIGINAL_DOCUMENT",
                    "verification_reference": r.rcept_no,
                    "resolution_note": reason,
                })
            elif "특수관계인의 유상증자 참여" in plain:
                semantic_status = "DIRECT_LISTED_ISSUER_ACTION_REQUIRES_REVIEW"
                reason = "RELATED_PARTY_PARTICIPATES_IN_LISTED_ISSUER_OFFERING"
            else:
                reason = "NO_EXPLICIT_SEPARATE_ACTION_ISSUER_STATEMENT"
        elif r.status == "AMBIGUOUS_DISCLOSURES":
            reason = "AMBIGUOUS_DISCLOSURE_MATCH"
        else:
            reason = f"DOCUMENT_STATUS_{r.status}"
        rows.append({
            "queue_event_id": r.queue_event_id, "code": str(r.code).zfill(6),
            "rcept_no": r.rcept_no, "document_status": r.status,
            "action_subject_type": subject_type, "semantic_status": semantic_status,
            "reason": reason,
            "promotion_status": "NOT_APPLICABLE_EVIDENCE" if semantic_status.startswith("EXPLICIT_NOT_APPLICABLE") else "NOT_PROMOTED",
        })
    audit = pd.DataFrame(rows)
    na = pd.DataFrame(evidence, columns=["queue_event_id", "verification_source",
                                        "verification_reference", "resolution_note"])
    ap, np = Path(audit_output_csv), Path(not_applicable_output_csv)
    ap.parent.mkdir(parents=True, exist_ok=True); np.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(ap, index=False, encoding="utf-8-sig")
    na.to_csv(np, index=False, encoding="utf-8-sig")
    return {"reviewed_rows": len(audit), "not_applicable_evidence_rows": len(na),
            "direct_issuer_review_rows": int(audit["semantic_status"].eq("DIRECT_LISTED_ISSUER_ACTION_REQUIRES_REVIEW").sum()),
            "unresolved_rows": int(audit["semantic_status"].eq("UNRESOLVED").sum()),
            "audit_output_csv": str(ap), "not_applicable_output_csv": str(np)}
