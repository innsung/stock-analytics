from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


def _plain(paths: list[Path]) -> str:
    raw = " ".join(path.read_text(encoding="utf-8") for path in paths)
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_historical_capital_reductions_v321(
    *, terms_csv: str, execution_manifest_csv: str, documents_dir: str,
    evidence_output_csv: str, audit_output_csv: str, summary_json: str,
) -> dict:
    terms = pd.read_csv(terms_csv, dtype=str).fillna("")
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    targets = terms[
        terms["mechanic_family"].eq("CAPITAL_REDUCTION")
        & terms["extraction_status"].eq("TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION")
    ].copy()
    descriptions = manifest.drop_duplicates("queue_event_id").set_index("queue_event_id")["source_description"]
    root = Path(documents_dir)
    evidence, audits = [], []
    for item in targets.itertuples(index=False):
        description = str(descriptions.get(item.queue_event_id, ""))
        paths = sorted(root.glob(f"{item.controlling_mechanics_rcept_no}_*"))
        try:
            text, error = (_plain(paths), "") if paths else ("", "DOCUMENT_NOT_FOUND")
        except (OSError, UnicodeError) as exc:
            text, error = "", f"{type(exc).__name__}: {exc}"
        subsidiary = "자회사의" in description or "종속회사의" in description
        reduction_confirmed = "감자" in text
        reduction_type = "PAID_REDUCTION" if "유상감자" in text else "FREE_REDUCTION" if "무상감자" in text else "OTHER_REDUCTION_TERMS"
        valid = bool(subsidiary and reduction_confirmed and paths and not error)
        status = "EXPLICIT_SUBSIDIARY_CAPITAL_REDUCTION" if valid else "LISTED_SHARE_REDUCTION_REVIEW_REQUIRED"
        reason = "SUBSIDIARY_CAPITAL_REDUCTION_HAS_NO_LISTED_PARENT_SHARE_CONSOLIDATION" if valid else error or "SUBSIDIARY_OR_REDUCTION_SEMANTICS_NOT_PROVEN"
        if valid:
            evidence.append({
                "queue_event_id": item.queue_event_id,
                "verification_source": "OPENDART_CONTROLLING_DOCUMENT_CAPITAL_REDUCTION_APPLICABILITY",
                "verification_reference": f"DART:{item.controlling_mechanics_rcept_no}",
                "resolution_note": reason,
            })
        audits.append({
            "queue_event_id": item.queue_event_id, "code": str(item.code).zfill(6),
            "controlling_rcept_no": item.controlling_mechanics_rcept_no,
            "subsidiary_disclosure": subsidiary, "reduction_semantics_confirmed": reduction_confirmed,
            "reduction_type": reduction_type, "capital_reduction_percent": item.ratio_or_allotment_candidate,
            "applicability_status": status, "resolution_note": reason,
            "promotion_status": "NOT_APPLICABLE_EVIDENCE" if valid else "NOT_PROMOTED",
            "error": error,
        })
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    type_counts = pd.Series([row["reduction_type"] for row in audits]).value_counts().to_dict()
    summary = {"target_rows": int(len(targets)), "not_applicable_evidence_rows": int(len(evidence)),
               "listed_reduction_review_rows": int(len(targets) - len(evidence)),
               "reduction_type_counts": {str(k): int(v) for k, v in type_counts.items()},
               "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp = Path(summary_json); sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
