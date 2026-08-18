from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup


QUEUE_EVENT_ID = "5432bce5e1925c59ed3b"
DECISION_RECEIPT = "20211028000438"
FIRST_PRICE_RECEIPT = "20210914800549"


def _rows(raw: str) -> list[str]:
    soup = BeautifulSoup(raw, "html.parser")
    return [" ".join(row.get_text(" ", strip=True).split()) for row in soup.find_all("tr")]


def _number_after(rows: list[str], label: str) -> float | None:
    for row in rows:
        compact = re.sub(r"\s+", "", row)
        if label in compact:
            tail = compact.split(label, 1)[-1].replace(",", "")
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)", tail)
            if match:
                return float(match.group(1))
    return None


def _date_after(rows: list[str], label: str) -> str:
    for row in rows:
        compact = re.sub(r"\s+", "", row)
        if label in compact:
            match = re.search(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})", compact.split(label, 1)[-1])
            if match:
                return f"{int(match.group(1)):04d}{int(match.group(2)):02d}{int(match.group(3)):02d}"
    return ""


def _load_close(frame: pd.DataFrame) -> pd.Series:
    close = next((column for column in frame.columns if str(column).lower() in {"종가", "close"}), None)
    if close is None:
        raise ValueError("OHLCV close column unavailable")
    return pd.to_numeric(frame[close], errors="coerce")


def verify_samsung_heavy_rights_v321(
    dart_client, provider, *, review_queue_csv: str,
    decision_documents_dir: str, output_documents_dir: str,
    evidence_output_csv: str, audit_output_csv: str, summary_json: str,
) -> dict:
    review = pd.read_csv(review_queue_csv, dtype=str).fillna("")
    target = review[review["queue_event_id"].eq(QUEUE_EVENT_ID)]
    root = Path(decision_documents_dir)
    decision_paths = sorted(root.glob(f"{DECISION_RECEIPT}_*"))
    if len(target) != 1 or not decision_paths:
        raise ValueError("Samsung Heavy rights target or controlling decision document unavailable")
    decision_raw = " ".join(path.read_text(encoding="utf-8") for path in decision_paths)
    decision_rows = _rows(decision_raw)
    final_price = _number_after(decision_rows, "확정발행가")
    record_date = _date_after(decision_rows, "신주배정기준일")
    allotment_ratio = _number_after(decision_rows, "1주당신주배정주식수(주)")

    out_root = Path(output_documents_dir); out_root.mkdir(parents=True, exist_ok=True)
    parts = dart_client.document_texts(FIRST_PRICE_RECEIPT)
    for index, part in enumerate(parts):
        (out_root / f"{FIRST_PRICE_RECEIPT}_{index:02d}_{part['name']}").write_text(part["text"], encoding="utf-8")
    price_rows = _rows(" ".join(part["text"] for part in parts))
    first_price = _number_after(price_rows, "보통주식(원)")

    raw = provider.ohlcv("20210901", "20210930", "010140", adjusted=False)
    adjusted = provider.ohlcv("20210901", "20210930", "010140", adjusted=True)
    common = raw.index.intersection(adjusted.index)
    raw_close, adjusted_close = _load_close(raw.loc[common]), _load_close(adjusted.loc[common])
    ratio = adjusted_close / raw_close
    changed = ratio[(ratio - 1.0).abs() > 1e-8]
    unchanged = ratio[(ratio - 1.0).abs() <= 1e-8]
    evidence = []
    status, reason = "UNRESOLVED", ""
    effective = pre_date = ""
    factor = theoretical_gap = None
    if changed.empty or unchanged.empty:
        reason = "KRX_ADJUSTED_RAW_RIGHTS_BOUNDARY_UNAVAILABLE"
    else:
        pre_index = changed.index.max()
        post = unchanged[unchanged.index > pre_index]
        if post.empty:
            reason = "KRX_POST_RIGHTS_BOUNDARY_UNAVAILABLE"
        else:
            effective_index = post.index.min()
            pre_date, effective = pre_index.strftime("%Y%m%d"), effective_index.strftime("%Y%m%d")
            raw_pre, adjusted_pre = float(raw_close.loc[pre_index]), float(adjusted_close.loc[pre_index])
            if first_price and allotment_ratio:
                theoretical = (raw_pre + allotment_ratio * first_price) / (1.0 + allotment_ratio)
                theoretical_gap = adjusted_pre / theoretical - 1.0
                factor = raw_pre / adjusted_pre
                valid = bool(final_price == first_price == 5130.0 and record_date == "20210917"
                             and abs(allotment_ratio - 0.3310433870) < 1e-10
                             and FIRST_PRICE_RECEIPT[:8] <= effective <= record_date
                             and abs(theoretical_gap) <= 0.01)
                if valid:
                    status = "STRICT_RIGHTS_EVIDENCE_READY"
                    evidence.append({
                        "queue_event_id": QUEUE_EVENT_ID, "code": "010140",
                        "event_family": "CORPORATE_ACTION", "source_reference_date": record_date,
                        "effective_date": effective, "known_at": FIRST_PRICE_RECEIPT[:8],
                        "action_type": "RIGHTS", "adjustment_factor": factor, "cash_amount": 0.0,
                        "verification_source": "OPENDART_PIT_RIGHTS_TERMS+KRX_ADJUSTED_RAW_BOUNDARY",
                        "verification_reference": f"DART:{DECISION_RECEIPT}|DART:{FIRST_PRICE_RECEIPT}",
                        "resolution_note": "RIGHTS_FACTOR_CONFIRMED_BY_PIT_THEORETICAL_EX_RIGHTS_PRICE",
                    })
                else:
                    reason = "RIGHTS_TERMS_OR_THEORETICAL_BOUNDARY_CHECK_FAILED"
            else:
                reason = "RIGHTS_PRICE_OR_ALLOTMENT_RATIO_MISSING"
    audit = pd.DataFrame([{
        "queue_event_id": QUEUE_EVENT_ID, "decision_rcept_no": DECISION_RECEIPT,
        "first_price_rcept_no": FIRST_PRICE_RECEIPT, "record_date": record_date,
        "allotment_ratio": allotment_ratio, "first_issue_price": first_price,
        "final_issue_price": final_price, "pre_boundary_date": pre_date,
        "effective_date": effective, "adjustment_factor": factor,
        "theoretical_gap": theoretical_gap, "verification_status": status, "reason": reason,
    }])
    columns = ["queue_event_id", "code", "event_family", "source_reference_date", "effective_date",
               "known_at", "action_type", "adjustment_factor", "cash_amount", "verification_source",
               "verification_reference", "resolution_note"]
    ep, ap = Path(evidence_output_csv), Path(audit_output_csv)
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    audit.to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": 1, "strict_evidence_rows": int(len(evidence)),
               "effective_date": effective, "adjustment_factor": factor,
               "theoretical_gap": theoretical_gap, "evidence_output_csv": str(ep),
               "audit_output_csv": str(ap), "documents_dir": str(out_root)}
    sp = Path(summary_json); sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
