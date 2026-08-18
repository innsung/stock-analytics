from __future__ import annotations

import re
import html
from pathlib import Path

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH


def _dates(text: str) -> list[str]:
    values = re.findall(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    return [f"{y}{int(m):02d}{int(d):02d}" for y, m, d in values]


def review_direct_action_groups_v321(
    *, inventory_csv: str, evidence_output_csv: str, audit_output_csv: str,
    parsed_documents_csv: str | None = None,
) -> dict:
    inventory = pd.read_csv(inventory_csv, dtype=str).fillna("")
    parsed = pd.read_csv(parsed_documents_csv, dtype=str).fillna("") if parsed_documents_csv else pd.DataFrame()
    evidence, audits = [], []
    for group_id, group in inventory.groupby("candidate_legal_event_group", sort=True):
        text = "\n".join(
            Path(p).read_text(encoding="utf-8", errors="ignore")
            for paths in group["document_paths"] for p in paths.split("|")
            if p and Path(p).exists()
        )
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))
        family = group.iloc[0]["action_family"]
        dates = _dates(text)
        future_markers = [d for d in dates if d > RESEARCH_SEEN_THROUGH]
        primary_qid = ""
        group_status = "CORE_EVENT_REQUIRES_MARKET_EVIDENCE"
        group_reason = ""
        if family == "RIGHTS_OFFERING" and future_markers and min(future_markers) > RESEARCH_SEEN_THROUGH:
            # Only use the rule when every explicit allotment/listing marker is outside
            # the research boundary; document and receipt dates may be earlier.
            explicit = re.findall(r"(?:신주배정기준일|신주의\s*상장예정일)[^0-9]{0,30}(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
            explicit_dates = [f"{y}{int(m):02d}{int(d):02d}" for y, m, d in explicit]
            if explicit_dates and min(explicit_dates) > RESEARCH_SEEN_THROUGH:
                group_status = "OUTSIDE_RESEARCH_WINDOW"
                group_reason = "ALL_EXPLICIT_MARKET_EFFECTIVE_MARKERS_AFTER_RESEARCH_CUTOFF"
        if family == "RIGHTS_OFFERING" and not parsed.empty:
            parsed_group = parsed[parsed["queue_event_id"].isin(group["queue_event_id"])]
            parsed_dates = [d for d in parsed_group["official_event_date_candidate"] if len(d) == 8 and d.isdigit()]
            if parsed_dates and min(parsed_dates) > RESEARCH_SEEN_THROUGH:
                group_status = "OUTSIDE_RESEARCH_WINDOW"
                group_reason = "PARSED_OFFICIAL_EVENT_DATES_AFTER_RESEARCH_CUTOFF"
        if family == "CAPITAL_REDUCTION" and "자기주식 소각" in text:
            group_status = "EXPLICIT_NOT_APPLICABLE"
            group_reason = "TREASURY_SHARE_CANCELLATION_NO_HOLDER_SHARE_ADJUSTMENT"
        if group_status == "CORE_EVENT_REQUIRES_MARKET_EVIDENCE":
            legal = group[group["source_description"].str.contains("주요사항보고서", regex=False)].copy()
            legal = legal[~legal["source_description"].str.contains("첨부정정", regex=False)]
            primary = legal.sort_values("source_reference_date").iloc[-1] if not legal.empty else group.sort_values("source_reference_date").iloc[-1]
            primary_qid = primary["queue_event_id"]
            group_reason = "LATEST_PRIMARY_LEGAL_FILING_RETAINED_FOR_EVENT_RESOLUTION"
        for row in group.itertuples(index=False):
            if group_status in {"OUTSIDE_RESEARCH_WINDOW", "EXPLICIT_NOT_APPLICABLE"}:
                row_status, reason = "NOT_APPLICABLE_EVIDENCE", group_reason
            elif row.queue_event_id == primary_qid:
                row_status, reason = "CORE_EVENT_UNRESOLVED", group_reason
            else:
                row_status = "NOT_APPLICABLE_EVIDENCE"
                reason = "SUPERSEDED_OR_SUPPORTING_DISCLOSURE_SAME_LEGAL_EVENT"
            if row_status == "NOT_APPLICABLE_EVIDENCE":
                evidence.append({"queue_event_id": row.queue_event_id,
                    "verification_source": "OPENDART_LEGAL_EVENT_GROUP_REVIEW",
                    "verification_reference": row.rcept_no or group_id,
                    "resolution_note": reason})
            audits.append({"queue_event_id": row.queue_event_id, "code": row.code,
                "candidate_legal_event_group": group_id, "group_status": group_status,
                "row_status": row_status, "primary_queue_event_id": primary_qid,
                "reason": reason, "promotion_status": "NOT_APPLICABLE_EVIDENCE" if row_status == "NOT_APPLICABLE_EVIDENCE" else "NOT_PROMOTED"})
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    ep.parent.mkdir(parents=True, exist_ok=True); ap.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(evidence, columns=["queue_event_id", "verification_source", "verification_reference", "resolution_note"]).to_csv(ep, index=False, encoding="utf-8-sig")
    audit = pd.DataFrame(audits); audit.to_csv(ap, index=False, encoding="utf-8-sig")
    return {"reviewed_groups": int(inventory["candidate_legal_event_group"].nunique()),
            "reviewed_rows": len(audit), "not_applicable_evidence_rows": len(evidence),
            "core_unresolved_rows": int(audit["row_status"].eq("CORE_EVENT_UNRESOLVED").sum()),
            "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
