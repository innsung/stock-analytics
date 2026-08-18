from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd


def _plain(parts: list[dict[str, str]]) -> str:
    text = "\n".join(p["text"] for p in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))


def resolve_residual_subsidiary_actions_v321(
    dart_client, *, applicability_audit_csv: str, acquisition_manifest_csv: str,
    disclosures_csv: str, documents_dir: str, evidence_output_csv: str,
    audit_output_csv: str,
) -> dict:
    audit = pd.read_csv(applicability_audit_csv, dtype=str).fillna("")
    acquisition = pd.read_csv(acquisition_manifest_csv, dtype=str).fillna("").set_index("queue_event_id")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    disclosures["code"] = disclosures["code"].astype(str).str.zfill(6)
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    evidence, audits = [], []
    residual = audit[~audit["semantic_status"].eq("EXPLICIT_NOT_APPLICABLE_TO_PARENT_SECURITY")]
    for row in residual.itertuples(index=False):
        status, reason, refs = "UNRESOLVED", "", []
        if row.semantic_status == "DIRECT_LISTED_ISSUER_ACTION_REQUIRES_REVIEW":
            support_receipt = row.rcept_no
            support_plain = _plain(dart_client.document_texts(support_receipt))
            source_date = acquisition.loc[row.queue_event_id, "source_reference_date"]
            candidates = disclosures[
                disclosures["code"].eq(str(row.code).zfill(6))
                & disclosures["report_nm"].str.replace(" ", "", regex=False).str.contains(r"주요사항보고서\(유상증자결정\)", regex=True)
                & disclosures["rcept_dt"].le(source_date)
            ].copy()
            candidates["distance"] = (pd.to_datetime(source_date) - pd.to_datetime(candidates["rcept_dt"])).dt.days
            candidates = candidates[candidates["distance"].between(0, 2)].sort_values("distance")
            if len(candidates) == 1 and ("유상증자 참여" in support_plain):
                main_receipt = candidates.iloc[0]["rcept_no"]
                refs = [support_receipt, main_receipt]
                status = "EXPLICIT_NOT_APPLICABLE_SUPPORTING_NOTICE"
                reason = "RELATED_PARTY_PARTICIPATION_NOTICE_LINKED_TO_PRIMARY_RIGHTS_OFFERING"
        elif row.document_status == "AMBIGUOUS_DISCLOSURES":
            refs = [x for x in acquisition.loc[row.queue_event_id, "error"].split("|") if x]
            verified = []
            for receipt in refs:
                parts = dart_client.document_texts(receipt)
                plain = _plain(parts)
                verified.append(
                    ("종속회사인" in plain or "[종속회사에 관한 사항]" in plain)
                    and "종속회사명" in plain
                )
                for index, part in enumerate(parts):
                    path = root / f"{receipt}_{index:02d}_{part['name']}"
                    path.write_text(part["text"], encoding="utf-8")
            if len(refs) == 2 and all(verified):
                status = "EXPLICIT_NOT_APPLICABLE_AMBIGUOUS_SET"
                reason = "ALL_AMBIGUOUS_DOCUMENTS_ARE_SEPARATE_SUBSIDIARY_ACTIONS"
        if status.startswith("EXPLICIT_NOT_APPLICABLE"):
            evidence.append({"queue_event_id": row.queue_event_id,
                "verification_source": "OPENDART_CROSS_DOCUMENT_SEMANTIC_LINK",
                "verification_reference": "|".join(refs), "resolution_note": reason})
        audits.append({"queue_event_id": row.queue_event_id, "code": str(row.code).zfill(6),
                       "semantic_status": status, "references": "|".join(refs),
                       "reason": reason, "promotion_status": "NOT_APPLICABLE_EVIDENCE" if status.startswith("EXPLICIT_NOT_APPLICABLE") else "NOT_PROMOTED"})
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    ep.parent.mkdir(parents=True, exist_ok=True); ap.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(evidence, columns=["queue_event_id", "verification_source", "verification_reference", "resolution_note"]).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    return {"reviewed_rows": len(audits), "not_applicable_evidence_rows": len(evidence),
            "unresolved_rows": len(audits) - len(evidence), "evidence_output_csv": str(ep),
            "audit_output_csv": str(ap), "documents_dir": str(root)}
