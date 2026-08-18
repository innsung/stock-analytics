import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.ml.official_event_resolver_v321 import (
    prepare_official_event_evidence_template_v321,
    read_official_event_evidence_v321,
    resolve_official_events_v321,
)


def _verification(path: Path):
    pd.DataFrame([
        {
            "queue_event_id": "q1",
            "code": "005930",
            "event_family": "DIVIDEND_OR_DISTRIBUTION",
            "source_reference_date": "20230307",
            "source_description": "annual dividend",
            "resolution_status": "UNRESOLVED",
            "effective_date": "", "known_at": "", "action_type": "",
            "adjustment_factor": "", "cash_amount": "",
            "verification_source": "", "verification_reference": "",
            "resolution_note": "",
        },
        {
            "queue_event_id": "q2",
            "code": "005930",
            "event_family": "CORPORATE_ACTION",
            "source_reference_date": "20200601",
            "source_description": "주식분할 결정",
            "resolution_status": "UNRESOLVED",
            "effective_date": "", "known_at": "", "action_type": "",
            "adjustment_factor": "", "cash_amount": "",
            "verification_source": "", "verification_reference": "",
            "resolution_note": "",
        },
    ]).to_csv(path, index=False, encoding="utf-8-sig")


def test_prepare_official_evidence_template(tmp_path):
    v = tmp_path / "verification.csv"
    _verification(v)
    out = tmp_path / "evidence.csv"
    result = prepare_official_event_evidence_template_v321(
        verification_csv=str(v), output_csv=str(out)
    )
    assert result["rows"] == 2
    f = pd.read_csv(out, dtype=str).fillna("")
    assert set(f["queue_event_id"]) == {"q1", "q2"}
    assert f["verification_source"].eq("").all()


def test_strict_evidence_rejects_placeholder_and_future(tmp_path):
    p = tmp_path / "evidence.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307","effective_date":"20270101","known_at":"20261231",
        "action_type":"CASH_DIVIDEND","adjustment_factor":"1","cash_amount":"100",
        "verification_source":"PLACEHOLDER","verification_reference":"x",
    }]).to_csv(p,index=False)
    f, ok, status = read_official_event_evidence_v321(str(p))
    assert not ok
    assert status == "INVALID_OFFICIAL_EVENT_EVIDENCE"


def test_resolver_unique_verified_match(tmp_path):
    v = tmp_path / "verification.csv"
    _verification(v)
    e = tmp_path / "evidence.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307","effective_date":"20221228","known_at":"20221215",
        "action_type":"CASH_DIVIDEND","adjustment_factor":"1","cash_amount":"100",
        "verification_source":"OFFICIAL_KRX","verification_reference":"ref1",
    }]).to_csv(e,index=False)
    result = resolve_official_events_v321(
        verification_csv=str(v), evidence_csv=str(e),
        output_csv=str(tmp_path/"resolved.csv"), audit_csv=str(tmp_path/"audit.csv"),
    )
    assert result["verified_queue_events"] == 1
    assert result["unresolved_queue_events"] == 1
    out = pd.read_csv(tmp_path/"resolved.csv", dtype=str).fillna("")
    q1 = out[out["queue_event_id"]=="q1"].iloc[0]
    assert q1["resolution_status"] == "VERIFIED"
    assert q1["effective_date"] == "20221228"


def test_resolver_expands_multiple_dividend_events(tmp_path):
    v = tmp_path / "verification.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307","source_description":"annual",
        "resolution_status":"UNRESOLVED","effective_date":"","known_at":"","action_type":"",
        "adjustment_factor":"","cash_amount":"","verification_source":"",
        "verification_reference":"","resolution_note":"",
    }]).to_csv(v,index=False)
    e = tmp_path / "evidence.csv"
    pd.DataFrame([
        {"queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
         "source_reference_date":"20230307","effective_date":"20220629","known_at":"20220615",
         "action_type":"CASH_DIVIDEND","adjustment_factor":"1","cash_amount":"50",
         "verification_source":"OFFICIAL_A","verification_reference":"a"},
        {"queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
         "source_reference_date":"20230307","effective_date":"20221228","known_at":"20221215",
         "action_type":"CASH_DIVIDEND","adjustment_factor":"1","cash_amount":"100",
         "verification_source":"OFFICIAL_B","verification_reference":"b"},
    ]).to_csv(e,index=False)
    result = resolve_official_events_v321(
        verification_csv=str(v), evidence_csv=str(e),
        output_csv=str(tmp_path/"resolved.csv"), audit_csv=str(tmp_path/"audit.csv"),
    )
    assert result["verified_queue_events"] == 1
    out = pd.read_csv(tmp_path/"resolved.csv")
    assert len(out) == 2


def test_not_applicable_requires_explicit_evidence(tmp_path):
    v = tmp_path / "verification.csv"
    _verification(v)
    e = tmp_path / "evidence.csv"
    # Need at least one valid evidence row to pass evidence-file validation.
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date":"20230307","effective_date":"20221228","known_at":"20221215",
        "action_type":"CASH_DIVIDEND","adjustment_factor":"1","cash_amount":"100",
        "verification_source":"OFFICIAL","verification_reference":"ref",
    }]).to_csv(e,index=False)
    na = tmp_path / "na.csv"
    pd.DataFrame([{
        "queue_event_id":"q2","verification_source":"OFFICIAL_DOC_REVIEW",
        "verification_reference":"doc","resolution_note":"false positive disclosure candidate"
    }]).to_csv(na,index=False)
    result = resolve_official_events_v321(
        verification_csv=str(v), evidence_csv=str(e),
        output_csv=str(tmp_path/"resolved.csv"), audit_csv=str(tmp_path/"audit.csv"),
        not_applicable_csv=str(na),
    )
    assert result["not_applicable_queue_events"] == 1
    assert result["unresolved_queue_events"] == 0


def test_main_namespace_contains_phase53_54_55_functions():
    m = importlib.import_module("src.main")
    expected = [
        "acquire_payout_action_facts_v321",
        "build_event_reconciliation_template_v321",
        "prepare_event_verification_v321",
        "finalize_event_reconciliation_v321",
        "prepare_official_event_evidence_template_v321",
        "resolve_official_events_v321",
    ]
    for name in expected:
        assert hasattr(m, name), name
