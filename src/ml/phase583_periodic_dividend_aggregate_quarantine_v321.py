from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def quarantine_periodic_dividend_aggregates_v321(
    *, execution_manifest_csv: str, dividend_facts_csv: str,
    evidence_output_csv: str, audit_output_csv: str,
    replacement_queue_csv: str, summary_json: str,
) -> dict:
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    facts = pd.read_csv(dividend_facts_csv, dtype=str).fillna("")
    required_manifest = {"queue_event_id", "code", "source_reference_date", "source_description",
                         "execution_lane", "resolution_status"}
    required_facts = {"code", "business_year", "raw_json", "promotion_status"}
    if missing := sorted(required_manifest - set(manifest.columns)):
        raise ValueError("execution manifest missing columns: " + ", ".join(missing))
    if missing := sorted(required_facts - set(facts.columns)):
        raise ValueError("dividend facts missing columns: " + ", ".join(missing))

    targets = manifest[manifest["execution_lane"].eq("DIVIDEND_DECISION_EXDATE_LINKAGE")].copy()
    facts["code"] = facts["code"].astype(str).str.zfill(6)
    evidence: list[dict[str, str]] = []
    audits: list[dict[str, str | int | bool]] = []
    replacements: list[dict[str, str]] = []

    for target in targets.itertuples(index=False):
        business_year = str(target.source_description)[-4:]
        group = facts[(facts["code"].eq(str(target.code).zfill(6))) &
                      (facts["business_year"].eq(business_year))]
        receipts: set[str] = set()
        settlement_dates: set[str] = set()
        parse_errors: list[str] = []
        for raw in group["raw_json"]:
            try:
                payload = json.loads(raw)
                receipts.add(str(payload.get("rcept_no", "")))
                settlement_dates.add(str(payload.get("stlm_dt", "")))
            except (TypeError, json.JSONDecodeError) as exc:
                parse_errors.append(f"{type(exc).__name__}: {exc}")
        receipts.discard("")
        settlement_dates.discard("")
        receipt = next(iter(receipts), "") if len(receipts) == 1 else ""
        actual_known_at = receipt[:8] if len(receipt) >= 8 else ""
        expected_settlement = f"{business_year}-12-31"
        source_fact_only = bool(len(group) and group["promotion_status"].eq(
            "DISCLOSURE_FACT_ONLY_NOT_EFFECTIVE_CASH_EVENT").all())
        valid = bool(
            str(target.resolution_status) == "UNRESOLVED"
            and business_year.isdigit()
            and len(group) > 0
            and len(receipts) == 1
            and settlement_dates == {expected_settlement}
            and source_fact_only
            and not parse_errors
            and actual_known_at >= str(target.source_reference_date)
        )
        status = "PERIODIC_AGGREGATE_CONFIRMED_NOT_DISCRETE_EVENT" if valid else "QUARANTINE_VALIDATION_FAILED"
        reason = (
            "ANNUAL_ALOT_MATTER_AGGREGATE_HAS_NO_UNIQUE_EXDATE_OR_PAYMENT_EVENT"
            if valid else "|".join(parse_errors) or "SOURCE_OR_TEMPORAL_INVARIANT_FAILED"
        )
        if valid:
            evidence.append({
                "queue_event_id": target.queue_event_id,
                "verification_source": "OPENDART_PERIODIC_AGGREGATE_SEMANTIC_AUDIT",
                "verification_reference": f"DART:{receipt}",
                "resolution_note": reason,
            })
            replacements.append({
                "source_queue_event_id": target.queue_event_id,
                "code": str(target.code).zfill(6),
                "business_year": business_year,
                "annual_report_rcept_no": receipt,
                "actual_known_at": actual_known_at,
                "settlement_date": expected_settlement.replace("-", ""),
                "required_evidence": "EACH_DIRECT_DIVIDEND_DECISION+OFFICIAL_MARKET_EXDATE",
                "replacement_status": "REQUIRES_DISCRETE_DIVIDEND_EVENT_RECONSTRUCTION",
                "pit_guard": "DO_NOT_USE_ANNUAL_AGGREGATE_AS_EVENT_OR_KNOWN_AT",
            })
        audits.append({
            "queue_event_id": target.queue_event_id,
            "code": str(target.code).zfill(6),
            "business_year": business_year,
            "queue_source_reference_date": target.source_reference_date,
            "actual_annual_report_known_at": actual_known_at,
            "fact_rows": int(len(group)),
            "unique_receipts": int(len(receipts)),
            "settlement_dates": "|".join(sorted(settlement_dates)),
            "source_fact_only": source_fact_only,
            "temporal_mismatch_confirmed": bool(actual_known_at > str(target.source_reference_date)),
            "quarantine_status": status,
            "reason": reason,
        })

    evidence_columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    replacement_columns = ["source_queue_event_id", "code", "business_year", "annual_report_rcept_no",
                           "actual_known_at", "settlement_date", "required_evidence",
                           "replacement_status", "pit_guard"]
    outputs = [
        (pd.DataFrame(evidence, columns=evidence_columns), Path(evidence_output_csv)),
        (pd.DataFrame(audits), Path(audit_output_csv)),
        (pd.DataFrame(replacements, columns=replacement_columns), Path(replacement_queue_csv)),
    ]
    for frame, path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    summary = {
        "target_rows": int(len(targets)),
        "quarantined_not_applicable_rows": int(len(evidence)),
        "validation_failed_rows": int(len(targets) - len(evidence)),
        "temporal_mismatch_rows": int(sum(bool(row["temporal_mismatch_confirmed"]) for row in audits)),
        "replacement_requirements": int(len(replacements)),
        "resolution_semantics": "SOURCE_PLACEHOLDER_NOT_APPLICABLE; UNDERLYING_DIVIDENDS_STILL_REQUIRED",
        "evidence_output_csv": str(Path(evidence_output_csv)),
        "audit_output_csv": str(Path(audit_output_csv)),
        "replacement_queue_csv": str(Path(replacement_queue_csv)),
    }
    path = Path(summary_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(path)}
