from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ml.phase565_strict_evidence_integration_v321 import integrate_strict_event_evidence_v321


def integrate_historical_dividend_evidence_v321(
    *, verification_csv: str, strict_ledger_csv: str, selected_evidence_csv: str,
    selection_audit_csv: str, output_csv: str, integration_audit_csv: str,
    priority_output_csv: str, priority_summary_json: str,
) -> dict:
    verification = pd.read_csv(verification_csv, dtype=str).fillna("")
    ledger = pd.read_csv(strict_ledger_csv, dtype=str).fillna("")
    unknown = sorted(set(ledger["queue_event_id"]) - set(verification["queue_event_id"]))
    if unknown:
        raise ValueError("unknown strict ledger queue_event_id: " + ", ".join(unknown[:5]))
    ledger = ledger.sort_values(["queue_event_id", "effective_date", "known_at"])
    selected = ledger.drop_duplicates("queue_event_id", keep="last").copy()
    selected_ids = set(zip(selected["queue_event_id"], selected["effective_date"], selected["known_at"]))
    audit = ledger.copy()
    audit["selection_status"] = [
        "SELECTED_LATEST_EVENT_FOR_ANNUAL_QUEUE" if (r.queue_event_id, r.effective_date, r.known_at) in selected_ids
        else "PRESERVED_IN_STRICT_LEDGER_NOT_QUEUE_SUMMARY"
        for r in ledger.itertuples(index=False)
    ]
    sp, ap = Path(selected_evidence_csv), Path(selection_audit_csv)
    sp.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(sp, index=False, encoding="utf-8-sig")
    audit.to_csv(ap, index=False, encoding="utf-8-sig")
    result = integrate_strict_event_evidence_v321(
        verification_csv=verification_csv, evidence_csv=str(sp), output_csv=output_csv,
        audit_csv=integration_audit_csv, priority_output_csv=priority_output_csv,
        priority_summary_json=priority_summary_json)
    result.update({
        "strict_ledger_rows": len(ledger), "selected_queue_rows": len(selected),
        "ledger_only_rows": len(ledger) - len(selected),
        "selected_evidence_csv": str(sp), "selection_audit_csv": str(ap),
    })
    return result
