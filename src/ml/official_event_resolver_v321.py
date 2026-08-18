from __future__ import annotations

from pathlib import Path
import json
import re

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

EVIDENCE_COLUMNS = {
    "code", "event_family", "effective_date", "known_at", "action_type",
    "adjustment_factor", "cash_amount", "verification_source",
    "verification_reference",
}
ALLOWED_FAMILIES = {"DIVIDEND_OR_DISTRIBUTION", "CORPORATE_ACTION"}
ALLOWED_ACTIONS = {
    "SPLIT", "REVERSE_SPLIT", "RIGHTS", "BONUS",
    "MERGER", "SPINOFF", "CASH_DIVIDEND", "ETF_DISTRIBUTION",
}
PLACEHOLDER = re.compile(r"REPLACE_WITH|PLACEHOLDER|EXAMPLE|TODO|TBD", re.I)


def _date(value) -> str:
    return str(value or "").replace("-", "").replace(".", "").strip()


def read_official_event_evidence_v321(path: str) -> tuple[pd.DataFrame, bool, str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"official event evidence CSV가 없습니다: {p}")
    f = pd.read_csv(p, dtype=str).fillna("")
    missing = EVIDENCE_COLUMNS - set(f.columns)
    if missing:
        raise ValueError("official event evidence CSV 누락 열: " + ", ".join(sorted(missing)))

    f["code"] = f["code"].str.strip().str.zfill(6)
    f["event_family"] = f["event_family"].str.strip().str.upper()
    f["effective_date"] = f["effective_date"].map(_date)
    f["known_at"] = f["known_at"].map(_date)
    f["action_type"] = f["action_type"].str.strip().str.upper()
    f["adjustment_factor"] = pd.to_numeric(f["adjustment_factor"], errors="coerce")
    f["cash_amount"] = pd.to_numeric(f["cash_amount"], errors="coerce")
    if "source_reference_date" in f.columns:
        f["source_reference_date"] = f["source_reference_date"].map(_date)
    else:
        f["source_reference_date"] = ""
    if "queue_event_id" not in f.columns:
        f["queue_event_id"] = ""

    invalid = (
        ~f["event_family"].isin(ALLOWED_FAMILIES)
        | ~f["action_type"].isin(ALLOWED_ACTIONS)
        | f["effective_date"].str.len().ne(8)
        | f["known_at"].str.len().ne(8)
        | f["effective_date"].gt(RESEARCH_SEEN_THROUGH)
        | f["known_at"].gt(f["effective_date"])
        | f["adjustment_factor"].isna() | f["adjustment_factor"].le(0)
        | f["cash_amount"].isna() | f["cash_amount"].lt(0)
        | f["verification_source"].str.strip().eq("")
        | f["verification_source"].str.contains(PLACEHOLDER)
    )
    dividend = f["event_family"].eq("DIVIDEND_OR_DISTRIBUTION")
    invalid |= dividend & ~f["action_type"].isin({"CASH_DIVIDEND", "ETF_DISTRIBUTION"})
    invalid |= dividend & f["adjustment_factor"].sub(1.0).abs().gt(1e-12)
    invalid |= dividend & f["cash_amount"].le(0)
    f["row_valid"] = ~invalid
    verified = bool(not f.empty and f["row_valid"].all())
    return f, verified, "VERIFIED_OFFICIAL_EVENT_EVIDENCE" if verified else "INVALID_OFFICIAL_EVENT_EVIDENCE"


def prepare_official_event_evidence_template_v321(*, verification_csv: str, output_csv: str) -> dict:
    """Create a clean evidence-import template from unresolved verification rows."""
    v = pd.read_csv(verification_csv, dtype=str).fillna("")
    required = {"queue_event_id", "code", "event_family", "source_reference_date", "source_description"}
    missing = required - set(v.columns)
    if missing:
        raise ValueError("verification CSV 누락 열: " + ", ".join(sorted(missing)))
    base = v.drop_duplicates("queue_event_id").copy()
    out = pd.DataFrame({
        "queue_event_id": base["queue_event_id"],
        "code": base["code"].astype(str).str.zfill(6),
        "event_family": base["event_family"],
        "source_reference_date": base["source_reference_date"],
        "effective_date": "",
        "known_at": "",
        "action_type": "",
        "adjustment_factor": "",
        "cash_amount": "",
        "verification_source": "",
        "verification_reference": "",
        "resolution_note": "",
    })
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False, encoding="utf-8-sig")
    return {"rows": int(len(out)), "output_csv": str(target)}


def _eligible_matches(queue_row: pd.Series, evidence: pd.DataFrame, date_window_days: int) -> pd.DataFrame:
    code = str(queue_row["code"]).zfill(6)
    family = str(queue_row["event_family"]).upper()
    candidates = evidence[
        evidence["code"].eq(code) & evidence["event_family"].eq(family)
    ].copy()
    if candidates.empty:
        return candidates

    qid = str(queue_row.get("queue_event_id", ""))
    exact = candidates[candidates["queue_event_id"].eq(qid) & candidates["queue_event_id"].ne("")]
    if not exact.empty:
        return exact

    ref = _date(queue_row.get("source_reference_date", ""))
    with_ref = candidates[candidates["source_reference_date"].eq(ref) & candidates["source_reference_date"].ne("")]
    if not with_ref.empty:
        return with_ref

    # Conservative fallback only for nearby dates. Annual dividend disclosures can
    # occur after the actual ex-date, so use a bounded symmetric distance. Ambiguity
    # remains unresolved instead of choosing one arbitrarily.
    if len(ref) == 8 and ref.isdigit():
        ref_dt = pd.to_datetime(ref, format="%Y%m%d")
        eff = pd.to_datetime(candidates["effective_date"], format="%Y%m%d", errors="coerce")
        dist = (eff - ref_dt).abs().dt.days
        return candidates[dist.le(int(date_window_days))]
    return candidates.iloc[0:0]


def resolve_official_events_v321(
    *,
    verification_csv: str,
    evidence_csv: str,
    output_csv: str,
    audit_csv: str,
    not_applicable_csv: str | None = None,
    date_window_days: int = 370,
) -> dict:
    """Merge strict official evidence into the Phase 5.4 verification sheet.

    No heuristic ever marks an event VERIFIED or NOT_APPLICABLE. VERIFIED requires
    a validated evidence row. NOT_APPLICABLE requires an explicit evidence file.
    Ambiguous or missing matches remain UNRESOLVED.
    """
    vpath = Path(verification_csv)
    if not vpath.exists():
        raise FileNotFoundError(f"verification CSV가 없습니다: {vpath}")
    v = pd.read_csv(vpath, dtype=str).fillna("")
    required = {
        "queue_event_id", "code", "event_family", "source_reference_date",
        "source_description", "resolution_status", "effective_date", "known_at",
        "action_type", "adjustment_factor", "cash_amount", "verification_source",
        "verification_reference", "resolution_note",
    }
    missing = required - set(v.columns)
    if missing:
        raise ValueError("verification CSV 누락 열: " + ", ".join(sorted(missing)))

    evidence, verified, status = read_official_event_evidence_v321(evidence_csv)
    if not verified:
        bad = int((~evidence["row_valid"]).sum()) if not evidence.empty else 0
        raise ValueError(f"official evidence 엄격 검증 실패: {status}, invalid_rows={bad}")
    evidence = evidence.drop(columns=["row_valid"])

    not_app = pd.DataFrame()
    if not_applicable_csv:
        npth = Path(not_applicable_csv)
        if not npth.exists():
            raise FileNotFoundError(f"NOT_APPLICABLE evidence CSV가 없습니다: {npth}")
        not_app = pd.read_csv(npth, dtype=str).fillna("")
        required_na = {"queue_event_id", "verification_source", "verification_reference", "resolution_note"}
        miss_na = required_na - set(not_app.columns)
        if miss_na:
            raise ValueError("NOT_APPLICABLE evidence 누락 열: " + ", ".join(sorted(miss_na)))
        bad_na = (
            not_app["queue_event_id"].str.strip().eq("")
            | not_app["verification_source"].str.strip().eq("")
            | not_app["verification_source"].str.contains(PLACEHOLDER)
            | not_app["resolution_note"].str.strip().eq("")
        )
        if bad_na.any():
            raise ValueError(f"NOT_APPLICABLE evidence invalid_rows={int(bad_na.sum())}")

    rows: list[dict] = []
    audit_rows: list[dict] = []
    for _, q in v.drop_duplicates("queue_event_id").iterrows():
        qid = q["queue_event_id"]
        matches = _eligible_matches(q, evidence, date_window_days)

        if len(matches) == 1:
            m = matches.iloc[0]
            r = q.to_dict()
            r.update({
                "resolution_status": "VERIFIED",
                "effective_date": m["effective_date"],
                "known_at": m["known_at"],
                "action_type": m["action_type"],
                "adjustment_factor": str(m["adjustment_factor"]),
                "cash_amount": str(m["cash_amount"]),
                "verification_source": m["verification_source"],
                "verification_reference": m["verification_reference"],
                "resolution_note": "AUTO_MATCHED_STRICT_OFFICIAL_EVIDENCE",
            })
            rows.append(r)
            resolution = "VERIFIED"
            note = "unique_match"
        elif len(matches) > 1:
            # Multiple events may legitimately belong to one annual dividend queue
            # row. Expand only if every match is a dividend/distribution event.
            dividend_group = (
                str(q["event_family"]).upper() == "DIVIDEND_OR_DISTRIBUTION"
                and matches["action_type"].isin({"CASH_DIVIDEND", "ETF_DISTRIBUTION"}).all()
            )
            if dividend_group:
                for _, m in matches.iterrows():
                    r = q.to_dict()
                    r.update({
                        "resolution_status": "VERIFIED",
                        "effective_date": m["effective_date"],
                        "known_at": m["known_at"],
                        "action_type": m["action_type"],
                        "adjustment_factor": str(m["adjustment_factor"]),
                        "cash_amount": str(m["cash_amount"]),
                        "verification_source": m["verification_source"],
                        "verification_reference": m["verification_reference"],
                        "resolution_note": "AUTO_EXPANDED_MULTI_CASH_EVENTS",
                    })
                    rows.append(r)
                resolution = "VERIFIED"
                note = f"expanded_{len(matches)}_cash_events"
            else:
                r = q.to_dict()
                r["resolution_status"] = "UNRESOLVED"
                r["resolution_note"] = f"AMBIGUOUS_OFFICIAL_EVIDENCE_MATCHES:{len(matches)}"
                rows.append(r)
                resolution = "UNRESOLVED"
                note = f"ambiguous_{len(matches)}"
        else:
            na = not_app[not_app["queue_event_id"].eq(qid)] if not not_app.empty else not_app
            if len(na) == 1:
                n = na.iloc[0]
                r = q.to_dict()
                r.update({
                    "resolution_status": "NOT_APPLICABLE",
                    "verification_source": n["verification_source"],
                    "verification_reference": n["verification_reference"],
                    "resolution_note": n["resolution_note"],
                })
                rows.append(r)
                resolution = "NOT_APPLICABLE"
                note = "explicit_not_applicable_evidence"
            else:
                r = q.to_dict()
                r["resolution_status"] = "UNRESOLVED"
                r["resolution_note"] = "NO_UNIQUE_OFFICIAL_EVIDENCE"
                rows.append(r)
                resolution = "UNRESOLVED"
                note = "no_match"

        audit_rows.append({
            "queue_event_id": qid,
            "code": str(q["code"]).zfill(6),
            "event_family": q["event_family"],
            "evidence_matches": int(len(matches)),
            "resolution": resolution,
            "note": note,
        })

    out = pd.DataFrame(rows)
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False, encoding="utf-8-sig")
    audit = pd.DataFrame(audit_rows)
    apath = Path(audit_csv)
    apath.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(apath, index=False, encoding="utf-8-sig")

    counts = audit["resolution"].value_counts().to_dict() if not audit.empty else {}
    result = {
        "queue_events": int(len(audit)),
        "output_rows": int(len(out)),
        "verified_queue_events": int(counts.get("VERIFIED", 0)),
        "not_applicable_queue_events": int(counts.get("NOT_APPLICABLE", 0)),
        "unresolved_queue_events": int(counts.get("UNRESOLVED", 0)),
        "verification_output_csv": str(target),
        "audit_csv": str(apath),
        "evidence_status": status,
        "research_seen_through": RESEARCH_SEEN_THROUGH,
    }
    manifest = target.with_name(target.stem + "_resolver_manifest.json")
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["manifest"] = str(manifest)
    return result
