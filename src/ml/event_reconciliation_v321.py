from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re

import pandas as pd

from src.ml.data_integrity_v321 import (
    RESEARCH_SEEN_THROUGH,
    read_corporate_actions_csv_v321,
)

TERMINAL_STATUSES = {"VERIFIED", "NOT_APPLICABLE"}
ALL_STATUSES = TERMINAL_STATUSES | {"UNRESOLVED"}
ALLOWED_ACTIONS = {
    "SPLIT", "REVERSE_SPLIT", "RIGHTS", "BONUS",
    "MERGER", "SPINOFF", "CASH_DIVIDEND", "ETF_DISTRIBUTION",
}
PLACEHOLDER_SOURCE = re.compile(r"REPLACE_WITH|PLACEHOLDER|EXAMPLE|TBD|TODO", re.I)


def _clean_date(value) -> str:
    return str(value or "").replace("-", "").replace(".", "").strip()


def _event_id(row: pd.Series, ordinal: int) -> str:
    raw = "|".join([
        str(row.get("code", "")).zfill(6),
        str(row.get("event_family", "")),
        str(row.get("source_reference_date", "")),
        str(row.get("source_description", "")),
        str(ordinal),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def prepare_event_verification_v321(*, queue_csv: str, output_csv: str) -> dict:
    source = Path(queue_csv)
    if not source.exists():
        raise FileNotFoundError(f"이벤트 reconciliation queue가 없습니다: {source}")
    queue = pd.read_csv(source, dtype=str).fillna("")
    required = {"code", "event_family", "source_reference_date", "source_description"}
    missing = required - set(queue.columns)
    if missing:
        raise ValueError("reconciliation queue 누락 열: " + ", ".join(sorted(missing)))

    queue = queue.reset_index(drop=True)
    queue["queue_event_id"] = [_event_id(row, i) for i, (_, row) in enumerate(queue.iterrows())]
    queue["code"] = queue["code"].astype(str).str.zfill(6)

    verification = pd.DataFrame({
        "queue_event_id": queue["queue_event_id"],
        "code": queue["code"],
        "event_family": queue["event_family"],
        "source_reference_date": queue["source_reference_date"],
        "source_description": queue["source_description"],
        "resolution_status": "UNRESOLVED",
        "effective_date": "",
        "known_at": "",
        "action_type": "",
        "adjustment_factor": "",
        "cash_amount": "",
        "verification_source": "",
        "verification_reference": "",
        "resolution_note": "",
    })
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    verification.to_csv(out, index=False, encoding="utf-8-sig")

    registry = out.with_name(out.stem + "_queue_registry.csv")
    queue.to_csv(registry, index=False, encoding="utf-8-sig")
    return {
        "rows": int(len(verification)),
        "output_csv": str(out),
        "queue_registry": str(registry),
    }


def _validate_verified_row(row: pd.Series) -> list[str]:
    errors: list[str] = []
    family = str(row["event_family"])
    action = str(row["action_type"]).strip().upper()
    effective = _clean_date(row["effective_date"])
    known = _clean_date(row["known_at"])
    source = str(row["verification_source"]).strip()
    try:
        factor = float(row["adjustment_factor"])
    except Exception:
        factor = float("nan")
    try:
        cash = float(row["cash_amount"])
    except Exception:
        cash = float("nan")

    if action not in ALLOWED_ACTIONS:
        errors.append("INVALID_ACTION_TYPE")
    if len(effective) != 8 or not effective.isdigit() or effective > RESEARCH_SEEN_THROUGH:
        errors.append("INVALID_EFFECTIVE_DATE")
    if len(known) != 8 or not known.isdigit() or (len(effective) == 8 and known > effective):
        errors.append("INVALID_KNOWN_AT")
    if not source or PLACEHOLDER_SOURCE.search(source):
        errors.append("INVALID_VERIFICATION_SOURCE")
    if pd.isna(factor) or factor <= 0:
        errors.append("INVALID_ADJUSTMENT_FACTOR")
    if pd.isna(cash) or cash < 0:
        errors.append("INVALID_CASH_AMOUNT")

    if family == "DIVIDEND_OR_DISTRIBUTION":
        if action not in {"CASH_DIVIDEND", "ETF_DISTRIBUTION"}:
            errors.append("DIVIDEND_FAMILY_ACTION_MISMATCH")
        if not pd.isna(factor) and abs(factor - 1.0) > 1e-12:
            errors.append("DIVIDEND_FACTOR_MUST_BE_1")
        if not pd.isna(cash) and cash <= 0:
            errors.append("DIVIDEND_CASH_MUST_BE_POSITIVE")
    elif family == "CORPORATE_ACTION":
        # Cash distributions can also appear through corporate-action notices.
        if action not in {"CASH_DIVIDEND", "ETF_DISTRIBUTION"} and not pd.isna(cash) and cash != 0:
            errors.append("NON_CASH_ACTION_CASH_MUST_BE_0")
    else:
        errors.append("UNKNOWN_EVENT_FAMILY")
    return errors


def finalize_event_reconciliation_v321(
    *,
    verification_csv: str,
    queue_registry_csv: str,
    canonical_output_csv: str,
    audit_output_csv: str,
    coverage_json: str,
    coverage_start: str,
    coverage_end: str,
) -> dict:
    """Promote verified evidence only; unresolved rows block complete coverage.

    Multiple VERIFIED rows may reference one queue_event_id, supporting interim +
    final dividends or multiple cash events represented by one annual disclosure fact.
    """
    verify_path = Path(verification_csv)
    registry_path = Path(queue_registry_csv)
    if not verify_path.exists():
        raise FileNotFoundError(f"verification CSV가 없습니다: {verify_path}")
    if not registry_path.exists():
        raise FileNotFoundError(f"queue registry CSV가 없습니다: {registry_path}")

    v = pd.read_csv(verify_path, dtype=str).fillna("")
    registry = pd.read_csv(registry_path, dtype=str).fillna("")
    required_v = {
        "queue_event_id", "code", "event_family", "resolution_status",
        "effective_date", "known_at", "action_type", "adjustment_factor",
        "cash_amount", "verification_source", "verification_reference", "resolution_note",
    }
    missing = required_v - set(v.columns)
    if missing:
        raise ValueError("verification CSV 누락 열: " + ", ".join(sorted(missing)))
    if "queue_event_id" not in registry.columns:
        raise ValueError("queue registry에 queue_event_id가 없습니다.")

    registry_ids = set(registry["queue_event_id"])
    unknown_ids = sorted(set(v["queue_event_id"]) - registry_ids)
    if unknown_ids:
        raise ValueError("registry에 없는 queue_event_id: " + ", ".join(unknown_ids[:5]))

    v["resolution_status"] = v["resolution_status"].str.strip().str.upper()
    invalid_status = sorted(set(v["resolution_status"]) - ALL_STATUSES)
    if invalid_status:
        raise ValueError("허용되지 않은 resolution_status: " + ", ".join(invalid_status))

    audit_rows = []
    canonical_rows = []
    for i, row in v.iterrows():
        status = row["resolution_status"]
        errors: list[str] = []
        if status == "VERIFIED":
            errors = _validate_verified_row(row)
            if not errors:
                canonical_rows.append({
                    "code": str(row["code"]).zfill(6),
                    "effective_date": _clean_date(row["effective_date"]),
                    "action_type": str(row["action_type"]).strip().upper(),
                    "adjustment_factor": float(row["adjustment_factor"]),
                    "cash_amount": float(row["cash_amount"]),
                    "known_at": _clean_date(row["known_at"]),
                    "source": (
                        f"{str(row['verification_source']).strip()}"
                        + (f":{str(row['verification_reference']).strip()}" if str(row["verification_reference"]).strip() else "")
                    ),
                    "queue_event_id": row["queue_event_id"],
                })
        elif status == "NOT_APPLICABLE":
            if not str(row["resolution_note"]).strip():
                errors.append("NOT_APPLICABLE_REQUIRES_NOTE")

        audit_rows.append({
            "row_number": i + 2,
            "queue_event_id": row["queue_event_id"],
            "code": str(row["code"]).zfill(6),
            "event_family": row["event_family"],
            "resolution_status": status,
            "valid": not errors,
            "errors": "|".join(errors),
        })

    audit = pd.DataFrame(audit_rows)
    invalid_rows = int((~audit["valid"]).sum()) if not audit.empty else 0
    if invalid_rows:
        out_audit = Path(audit_output_csv)
        out_audit.parent.mkdir(parents=True, exist_ok=True)
        audit.to_csv(out_audit, index=False, encoding="utf-8-sig")
        raise ValueError(f"event verification 검증 실패: invalid_rows={invalid_rows}. audit={out_audit}")

    # Every queue event must have at least one terminal resolution to claim complete coverage.
    terminal_by_id = (
        v[v["resolution_status"].isin(TERMINAL_STATUSES)]
        .groupby("queue_event_id").size().to_dict()
    )
    unresolved_registry_ids = sorted(registry_ids - set(terminal_by_id))

    canonical = pd.DataFrame(canonical_rows)
    canonical_path = Path(canonical_output_csv)
    canonical_path.parent.mkdir(parents=True, exist_ok=True)

    strict_verified = False
    strict_status = "NO_VERIFIED_CANONICAL_EVENTS"
    if canonical.empty:
        canonical = pd.DataFrame(columns=[
            "code", "effective_date", "action_type", "adjustment_factor",
            "cash_amount", "known_at", "source", "queue_event_id",
        ])
        canonical.to_csv(canonical_path, index=False, encoding="utf-8-sig")
    else:
        # Canonical validator does not know queue_event_id; validate exact canonical fields.
        strict_cols = [
            "code", "effective_date", "action_type", "adjustment_factor",
            "cash_amount", "known_at", "source",
        ]
        strict_tmp = canonical_path.with_name(canonical_path.stem + "_strict_tmp.csv")
        canonical[strict_cols].to_csv(strict_tmp, index=False, encoding="utf-8-sig")
        strict_frame, strict_verified, strict_status = read_corporate_actions_csv_v321(str(strict_tmp))
        strict_tmp.unlink(missing_ok=True)
        if not strict_verified:
            raise ValueError(f"canonical corporate action 엄격 검증 실패: {strict_status}")
        # Keep traceability column in the audit-side canonical output.
        canonical.to_csv(canonical_path, index=False, encoding="utf-8-sig")

    audit_path = Path(audit_output_csv)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")

    start = _clean_date(coverage_start)
    end = _clean_date(coverage_end)
    if len(start) != 8 or len(end) != 8 or start > end or end > RESEARCH_SEEN_THROUGH:
        raise ValueError("coverage 기간이 잘못되었거나 연구 경계를 넘습니다.")

    complete = len(unresolved_registry_ids) == 0
    dividend_ids = set(registry.loc[registry["event_family"] == "DIVIDEND_OR_DISTRIBUTION", "queue_event_id"])
    action_ids = set(registry.loc[registry["event_family"] == "CORPORATE_ACTION", "queue_event_id"])
    resolved_ids = set(terminal_by_id)
    cash_complete = dividend_ids.issubset(resolved_ids)
    capital_complete = action_ids.issubset(resolved_ids)

    coverage = {
        "start": start,
        "end": end,
        "codes": sorted(registry["code"].astype(str).str.zfill(6).unique().tolist()),
        "cash_distributions_complete": bool(cash_complete),
        "capital_actions_complete": bool(capital_complete),
        "source": "PHASE5_4_RECONCILED_VERIFIED_EVENT_EVIDENCE",
        "queue_rows": int(len(registry)),
        "verified_canonical_events": int(len(canonical)),
        "unresolved_queue_events": int(len(unresolved_registry_ids)),
        "complete": bool(complete),
        "research_seen_through": RESEARCH_SEEN_THROUGH,
    }
    coverage_path = Path(coverage_json)
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "canonical_rows": int(len(canonical)),
        "queue_rows": int(len(registry)),
        "unresolved_queue_events": int(len(unresolved_registry_ids)),
        "cash_distributions_complete": bool(cash_complete),
        "capital_actions_complete": bool(capital_complete),
        "coverage_complete": bool(complete),
        "canonical_output_csv": str(canonical_path),
        "audit_output_csv": str(audit_path),
        "coverage_json": str(coverage_path),
        "strict_status": strict_status if not canonical.empty else "NO_VERIFIED_CANONICAL_EVENTS",
    }
