import json

import pandas as pd

from src.ml.phase583_periodic_dividend_aggregate_quarantine_v321 import (
    quarantine_periodic_dividend_aggregates_v321,
)


def test_quarantines_annual_aggregate_and_preserves_replacement_requirement(tmp_path):
    pd.DataFrame([{
        "queue_event_id": "q1", "code": "5930", "source_reference_date": "20240312",
        "source_description": "OpenDART alotMatter 2024",
        "execution_lane": "DIVIDEND_DECISION_EXDATE_LINKAGE", "resolution_status": "UNRESOLVED",
    }]).to_csv(tmp_path / "manifest.csv", index=False)
    raw = json.dumps({"rcept_no": "20250318000001", "stlm_dt": "2024-12-31"})
    pd.DataFrame([{
        "code": "005930", "business_year": "2024", "raw_json": raw,
        "promotion_status": "DISCLOSURE_FACT_ONLY_NOT_EFFECTIVE_CASH_EVENT",
    }]).to_csv(tmp_path / "facts.csv", index=False)

    result = quarantine_periodic_dividend_aggregates_v321(
        execution_manifest_csv=str(tmp_path / "manifest.csv"), dividend_facts_csv=str(tmp_path / "facts.csv"),
        evidence_output_csv=str(tmp_path / "evidence.csv"), audit_output_csv=str(tmp_path / "audit.csv"),
        replacement_queue_csv=str(tmp_path / "replacement.csv"), summary_json=str(tmp_path / "summary.json"))

    assert result["quarantined_not_applicable_rows"] == 1
    evidence = pd.read_csv(tmp_path / "evidence.csv", dtype=str)
    replacement = pd.read_csv(tmp_path / "replacement.csv", dtype=str)
    assert evidence.loc[0, "verification_reference"] == "DART:20250318000001"
    assert replacement.loc[0, "actual_known_at"] == "20250318"
    assert replacement.loc[0, "replacement_status"] == "REQUIRES_DISCRETE_DIVIDEND_EVENT_RECONSTRUCTION"


def test_fails_closed_when_queue_date_is_not_before_actual_receipt(tmp_path):
    pd.DataFrame([{
        "queue_event_id": "q1", "code": "005930", "source_reference_date": "20250319",
        "source_description": "OpenDART alotMatter 2024",
        "execution_lane": "DIVIDEND_DECISION_EXDATE_LINKAGE", "resolution_status": "UNRESOLVED",
    }]).to_csv(tmp_path / "manifest.csv", index=False)
    raw = json.dumps({"rcept_no": "20250318000001", "stlm_dt": "2024-12-31"})
    pd.DataFrame([{"code": "005930", "business_year": "2024", "raw_json": raw,
                   "promotion_status": "DISCLOSURE_FACT_ONLY_NOT_EFFECTIVE_CASH_EVENT"}]).to_csv(
                       tmp_path / "facts.csv", index=False)
    result = quarantine_periodic_dividend_aggregates_v321(
        execution_manifest_csv=str(tmp_path / "manifest.csv"), dividend_facts_csv=str(tmp_path / "facts.csv"),
        evidence_output_csv=str(tmp_path / "evidence.csv"), audit_output_csv=str(tmp_path / "audit.csv"),
        replacement_queue_csv=str(tmp_path / "replacement.csv"), summary_json=str(tmp_path / "summary.json"))
    assert result["quarantined_not_applicable_rows"] == 0
    assert result["validation_failed_rows"] == 1
