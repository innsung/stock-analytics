import pandas as pd

from src.ml.phase527_kind_reconciliation_v321 import reconcile_kind_dividend_candidates_v321


def test_reconcile_rejects_wrong_amount_and_preserves_official_fact(tmp_path):
    queue = tmp_path / "queue.csv"
    crosscheck = tmp_path / "crosscheck.csv"
    parsed = tmp_path / "parsed.csv"
    audit = tmp_path / "audit.csv"
    facts = tmp_path / "facts.csv"
    pd.DataFrame([{
        "queue_event_id": "q1", "code": "660", "candidate_cash_amount": "1200",
        "record_date": "20260531", "priority": "P1_RECORD_DATE_READY_FOR_MARKET_VERIFICATION",
    }]).to_csv(queue, index=False)
    pd.DataFrame([{
        "queue_event_id": "q1", "kind_acpt_no": "20260422000788", "kind_doc_no": "20260422002195",
    }]).to_csv(crosscheck, index=False)
    pd.DataFrame([{
        "kind_acpt_no": "20260422000788", "kind_doc_no": "20260422002195",
        "common_cash_amount": "375", "preferred_cash_amount": "", "total_cash_amount": "1000",
        "record_date": "20260531", "payment_date": "", "board_date": "20260422",
        "parse_status": "SUCCESS", "document_path": "document.html",
    }]).to_csv(parsed, index=False)

    result = reconcile_kind_dividend_candidates_v321(
        market_queue_csv=str(queue), crosscheck_csv=str(crosscheck), parsed_csv=str(parsed),
        audit_csv=str(audit), official_facts_csv=str(facts),
    )
    assert result["candidate_status_counts"] == {"REJECTED_AMOUNT_MISMATCH": 1}
    assert result["official_fact_rows"] == 1
    assert pd.read_csv(facts, dtype=str).iloc[0]["common_cash_amount"] == "375"
