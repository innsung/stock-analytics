import json
from pathlib import Path

import pandas as pd

from src.ml.payout_action_acquisition_v321 import (
    acquire_payout_action_facts_v321,
    build_event_reconciliation_template_v321,
)


class FakeDart:
    def corp_code_map(self):
        return {"005930": "00126380"}

    def dividend_matters(self, corp_code, year, report_code="11011"):
        assert corp_code == "00126380"
        if year == 2020:
            return [{"se": "주당 현금배당금(원)", "stock_knd": "보통주", "thstrm": "1000", "frmtrm": "900", "lwfr": "800"}]
        return []

    def disclosure_date(self, corp_code, year, report_code):
        return f"{year+1}0315" if year < 2026 else "20260315"

    def disclosure_list(self, corp_code, begin, end, page_count=100):
        year = begin[:4]
        if year == "2020":
            return [
                {"rcept_dt": "20200601", "report_nm": "주식분할 결정", "rcept_no": "1", "flr_nm": "테스트"},
                {"rcept_dt": "20200602", "report_nm": "기타경영사항", "rcept_no": "2", "flr_nm": "테스트"},
            ]
        return []


def test_acquire_raw_facts_never_promotes_to_total_return(tmp_path):
    result = acquire_payout_action_facts_v321(
        FakeDart(), codes=["005930"], start_year=2020, end_year=2020,
        output_dir=str(tmp_path), max_retries=1, sleep_seconds=0,
    )
    assert result["status"] == "RAW_DISCLOSURE_FACTS_ACQUIRED"
    assert result["total_return_ready"] is False
    assert result["canonical_corporate_actions_verified"] is False
    div = pd.read_csv(tmp_path / "dividend_disclosure_facts.csv", dtype=str)
    act = pd.read_csv(tmp_path / "corporate_action_disclosures.csv", dtype=str)
    assert len(div) == 1
    assert len(act) == 1
    assert "NOT_EFFECTIVE_CASH_EVENT" in div.iloc[0]["promotion_status"]
    assert "EFFECTIVE_DATE_NOT_VERIFIED" in act.iloc[0]["promotion_status"]


def test_reconciliation_queue_has_blank_effective_fields(tmp_path):
    result = acquire_payout_action_facts_v321(
        FakeDart(), codes=["005930"], start_year=2020, end_year=2020,
        output_dir=str(tmp_path), max_retries=1, sleep_seconds=0,
    )
    q = tmp_path / "queue.csv"
    built = build_event_reconciliation_template_v321(
        dividend_facts_csv=result["outputs"]["dividend_disclosure_facts"],
        action_disclosures_csv=result["outputs"]["corporate_action_disclosures"],
        output_csv=str(q),
    )
    assert built["rows"] == 2
    frame = pd.read_csv(q, dtype=str).fillna("")
    assert frame["candidate_effective_date"].eq("").all()
    assert frame["verification_status"].str.startswith("NEEDS_").all()


class PartialDart(FakeDart):
    def dividend_matters(self, corp_code, year, report_code="11011"):
        raise TimeoutError("timeout")


def test_partial_provider_failure_is_audited_not_verified(tmp_path):
    result = acquire_payout_action_facts_v321(
        PartialDart(), codes=["005930"], start_year=2020, end_year=2020,
        output_dir=str(tmp_path), max_retries=2, retry_backoff_seconds=0, sleep_seconds=0,
    )
    assert result["partial_year_requests"] == 1
    assert result["total_return_ready"] is False
    audit = pd.read_csv(tmp_path / "payout_action_acquisition_audit.csv")
    assert audit.iloc[0]["status"] == "PARTIAL"


def test_research_cutoff_caps_2026_disclosure_search(tmp_path):
    calls = []
    class CaptureDart(FakeDart):
        def disclosure_list(self, corp_code, begin, end, page_count=100):
            calls.append((begin, end))
            return []
    acquire_payout_action_facts_v321(
        CaptureDart(), codes=["005930"], start_year=2026, end_year=2027,
        output_dir=str(tmp_path), max_retries=1, sleep_seconds=0,
    )
    assert calls == [("20260101", "20260709")]
