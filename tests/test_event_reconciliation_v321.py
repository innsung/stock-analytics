import json
from pathlib import Path

import pandas as pd
import pytest

from src.ml.event_reconciliation_v321 import (
    prepare_event_verification_v321,
    finalize_event_reconciliation_v321,
)


def _queue(path: Path):
    pd.DataFrame([
        {
            "code": "005930",
            "event_family": "DIVIDEND_OR_DISTRIBUTION",
            "source_reference_date": "20230307",
            "source_description": "annual dividend fact",
        },
        {
            "code": "005930",
            "event_family": "CORPORATE_ACTION",
            "source_reference_date": "20200110",
            "source_description": "주식분할 결정",
        },
    ]).to_csv(path, index=False, encoding="utf-8-sig")


def test_prepare_verification_assigns_stable_ids(tmp_path):
    q = tmp_path / "queue.csv"
    _queue(q)
    out = tmp_path / "verify.csv"
    result = prepare_event_verification_v321(queue_csv=str(q), output_csv=str(out))
    assert result["rows"] == 2
    f = pd.read_csv(out, dtype=str)
    assert f["queue_event_id"].nunique() == 2
    assert f["resolution_status"].eq("UNRESOLVED").all()
    reg = pd.read_csv(result["queue_registry"], dtype=str)
    assert set(reg["queue_event_id"]) == set(f["queue_event_id"])


def test_finalize_blocks_unresolved_coverage(tmp_path):
    q = tmp_path / "queue.csv"
    _queue(q)
    out = tmp_path / "verify.csv"
    prepared = prepare_event_verification_v321(queue_csv=str(q), output_csv=str(out))
    result = finalize_event_reconciliation_v321(
        verification_csv=str(out),
        queue_registry_csv=prepared["queue_registry"],
        canonical_output_csv=str(tmp_path / "canonical.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        coverage_json=str(tmp_path / "coverage.json"),
        coverage_start="20200101",
        coverage_end="20260709",
    )
    assert result["coverage_complete"] is False
    assert result["unresolved_queue_events"] == 2
    coverage = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    assert coverage["cash_distributions_complete"] is False
    assert coverage["capital_actions_complete"] is False


def test_verified_and_not_applicable_can_complete_coverage(tmp_path):
    q = tmp_path / "queue.csv"
    _queue(q)
    out = tmp_path / "verify.csv"
    prepared = prepare_event_verification_v321(queue_csv=str(q), output_csv=str(out))
    v = pd.read_csv(out, dtype=str).fillna("")
    # Dividend: verified actual cash event.
    v.loc[0, "resolution_status"] = "VERIFIED"
    v.loc[0, "effective_date"] = "20221228"
    v.loc[0, "known_at"] = "20221215"
    v.loc[0, "action_type"] = "CASH_DIVIDEND"
    v.loc[0, "adjustment_factor"] = "1"
    v.loc[0, "cash_amount"] = "100"
    v.loc[0, "verification_source"] = "OFFICIAL_EXDATE_SOURCE"
    # Corporate disclosure was a false-positive candidate.
    v.loc[1, "resolution_status"] = "NOT_APPLICABLE"
    v.loc[1, "resolution_note"] = "No capital action after source-document review"
    v.to_csv(out, index=False, encoding="utf-8-sig")

    result = finalize_event_reconciliation_v321(
        verification_csv=str(out),
        queue_registry_csv=prepared["queue_registry"],
        canonical_output_csv=str(tmp_path / "canonical.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        coverage_json=str(tmp_path / "coverage.json"),
        coverage_start="20200101",
        coverage_end="20260709",
    )
    assert result["coverage_complete"] is True
    assert result["canonical_rows"] == 1
    canonical = pd.read_csv(tmp_path / "canonical.csv", dtype=str)
    assert canonical.iloc[0]["action_type"] == "CASH_DIVIDEND"


def test_one_queue_event_can_expand_to_multiple_verified_cash_events(tmp_path):
    q = tmp_path / "queue.csv"
    pd.DataFrame([{
        "code": "005930",
        "event_family": "DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date": "20230307",
        "source_description": "annual dividend fact",
    }]).to_csv(q, index=False)
    out = tmp_path / "verify.csv"
    prepared = prepare_event_verification_v321(queue_csv=str(q), output_csv=str(out))
    v = pd.read_csv(out, dtype=str).fillna("")
    second = v.iloc[0].copy()
    for row, date, cash in [(v.index[0], "20220629", "50"), (None, "20221228", "100")]:
        pass
    v.loc[0, ["resolution_status","effective_date","known_at","action_type","adjustment_factor","cash_amount","verification_source"]] = [
        "VERIFIED","20220629","20220615","CASH_DIVIDEND","1","50","OFFICIAL_A"
    ]
    second["resolution_status"] = "VERIFIED"
    second["effective_date"] = "20221228"
    second["known_at"] = "20221215"
    second["action_type"] = "CASH_DIVIDEND"
    second["adjustment_factor"] = "1"
    second["cash_amount"] = "100"
    second["verification_source"] = "OFFICIAL_B"
    v = pd.concat([v, pd.DataFrame([second])], ignore_index=True)
    v.to_csv(out, index=False)
    result = finalize_event_reconciliation_v321(
        verification_csv=str(out),
        queue_registry_csv=prepared["queue_registry"],
        canonical_output_csv=str(tmp_path / "canonical.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"),
        coverage_json=str(tmp_path / "coverage.json"),
        coverage_start="20200101", coverage_end="20260709",
    )
    assert result["canonical_rows"] == 2
    assert result["coverage_complete"] is True


def test_verified_requires_known_at_not_after_effective_date(tmp_path):
    q = tmp_path / "queue.csv"
    pd.DataFrame([{
        "code": "005930", "event_family": "DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date": "20230307", "source_description": "annual"
    }]).to_csv(q, index=False)
    out = tmp_path / "verify.csv"
    prepared = prepare_event_verification_v321(queue_csv=str(q), output_csv=str(out))
    v = pd.read_csv(out, dtype=str).fillna("")
    v.loc[0, ["resolution_status","effective_date","known_at","action_type","adjustment_factor","cash_amount","verification_source"]] = [
        "VERIFIED","20221228","20230307","CASH_DIVIDEND","1","100","OFFICIAL"
    ]
    v.to_csv(out, index=False)
    with pytest.raises(ValueError, match="invalid_rows=1"):
        finalize_event_reconciliation_v321(
            verification_csv=str(out),
            queue_registry_csv=prepared["queue_registry"],
            canonical_output_csv=str(tmp_path / "canonical.csv"),
            audit_output_csv=str(tmp_path / "audit.csv"),
            coverage_json=str(tmp_path / "coverage.json"),
            coverage_start="20200101", coverage_end="20260709",
        )
