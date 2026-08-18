from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


def _plain(paths: list[Path]) -> str:
    raw = " ".join(path.read_text(encoding="utf-8") for path in paths)
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_historical_rights_applicability_v321(
    *, terms_csv: str, execution_manifest_csv: str, documents_dir: str,
    evidence_output_csv: str, audit_output_csv: str, summary_json: str,
) -> dict:
    terms = pd.read_csv(terms_csv, dtype=str).fillna("")
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    targets = terms[
        terms["mechanic_family"].eq("RIGHTS_OFFERING")
        & terms["extraction_status"].eq("TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION")
    ].copy()
    descriptions = manifest.drop_duplicates("queue_event_id").set_index("queue_event_id")["source_description"]
    root = Path(documents_dir)
    evidence, audits = [], []
    for item in targets.itertuples(index=False):
        description = str(descriptions.get(item.queue_event_id, ""))
        paths = sorted(root.glob(f"{item.controlling_mechanics_rcept_no}_*"))
        try:
            text = _plain(paths) if paths else ""
            error = ""
        except (OSError, UnicodeError) as exc:
            text, error = "", f"{type(exc).__name__}: {exc}"
        subsidiary = "자회사의" in description or "종속회사의" in description
        public_offering = "일반공모" in text
        third_party = "제3자배정" in text
        shareholder_rights = "주주배정" in text or "주주우선공모" in text
        if subsidiary:
            status = "EXPLICIT_SUBSIDIARY_ISSUANCE_NOT_PARENT_SHARE_EVENT"
            reason = "SUBSIDIARY_RIGHTS_OFFERING_HAS_NO_LISTED_PARENT_SHARE_ADJUSTMENT"
        elif public_offering and not shareholder_rights:
            status = "EXPLICIT_PUBLIC_OFFERING_WITHOUT_PREEMPTIVE_RIGHTS"
            reason = "GENERAL_PUBLIC_OFFERING_HAS_NO_EXISTING_SHAREHOLDER_RIGHTS_EXDATE"
        elif third_party and not shareholder_rights:
            status = "EXPLICIT_THIRD_PARTY_ALLOTMENT"
            reason = "THIRD_PARTY_ALLOTMENT_HAS_NO_EXISTING_SHAREHOLDER_RIGHTS_EXDATE"
        elif shareholder_rights:
            status = "SHAREHOLDER_RIGHTS_TERP_VALIDATION_REQUIRED"
            reason = ""
        else:
            status = "ALLOTMENT_METHOD_UNRESOLVED"
            reason = error or "OFFICIAL_ALLOTMENT_METHOD_NOT_PROVEN"
        not_applicable = status.startswith("EXPLICIT_")
        if not_applicable:
            evidence.append({
                "queue_event_id": item.queue_event_id,
                "verification_source": "OPENDART_CONTROLLING_DOCUMENT_RIGHTS_APPLICABILITY",
                "verification_reference": f"DART:{item.controlling_mechanics_rcept_no}",
                "resolution_note": reason,
            })
        audits.append({
            "queue_event_id": item.queue_event_id, "code": str(item.code).zfill(6),
            "controlling_rcept_no": item.controlling_mechanics_rcept_no,
            "subsidiary_disclosure": subsidiary, "public_offering": public_offering,
            "third_party_allotment": third_party, "shareholder_rights": shareholder_rights,
            "applicability_status": status, "resolution_note": reason,
            "promotion_status": "NOT_APPLICABLE_EVIDENCE" if not_applicable else "NOT_PROMOTED",
        })
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    counts = pd.Series([row["applicability_status"] for row in audits]).value_counts().to_dict()
    summary = {
        "target_rows": int(len(targets)), "not_applicable_evidence_rows": int(len(evidence)),
        "shareholder_rights_terp_candidates": int(counts.get("SHAREHOLDER_RIGHTS_TERP_VALIDATION_REQUIRED", 0)),
        "unresolved_allotment_rows": int(counts.get("ALLOTMENT_METHOD_UNRESOLVED", 0)),
        "status_counts": {str(k): int(v) for k, v in counts.items()},
        "evidence_output_csv": str(ep), "audit_output_csv": str(ap),
    }
    sp = Path(summary_json); sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
