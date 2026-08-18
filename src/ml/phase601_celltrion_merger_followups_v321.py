from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


CORE_QUEUE_ID = "9aceae44b8a5ad259866"
FOLLOWUPS = {
    "a39756bdc372fe148ca9": ("20231228000578", "ISSUANCE_RESULT"),
    "767d92fda3f88dfdae07": ("20230818000437", "REGISTRATION_STATEMENT"),
    "3d0685cd3d663ea1e895": ("20230817800229", "TRADING_HALT"),
}


def _plain(parts: list[dict]) -> str:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _contains(text: str, *groups: tuple[str, ...]) -> bool:
    compact = re.sub(r"[\s,.:：()\-]", "", text)
    return all(any(re.sub(r"[\s,.:：()\-]", "", token) in compact for token in group) for group in groups)


def _date_in(text: str, year: str, month: str, day: str) -> bool:
    return bool(re.search(rf"{year}\D{{0,20}}{month}\D{{0,20}}{day}", text))


def audit_celltrion_merger_followups_v321(
    dart_client, *, actionable_queue_csv: str, phase591_audit_csv: str,
    documents_dir: str, evidence_output_csv: str, audit_output_csv: str,
    summary_json: str,
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    core = pd.read_csv(phase591_audit_csv, dtype=str).fillna("")
    core_row = core[core["queue_event_id"].eq(CORE_QUEUE_ID)]
    core_ok = len(core_row) == 1 and all(
        str(core_row.iloc[0].get(column, "")) == expected
        for column, expected in {
            "official_rcept_no": "20230817000203", "merger_date": "20231228",
            "new_share_listing_date": "20240112", "target_exchange_ratio": "0.4492620",
            "merger_consideration_new_shares": "73887750", "merger_date_breakpoints": "0",
            "listing_date_breakpoints": "0",
            "validation_status": "ACQUIRER_SHAREHOLDER_POSITION_UNCHANGED_NO_MARKET_FACTOR",
        }.items()
    )
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    evidence, audits = [], []
    for queue_id, (receipt, kind) in FOLLOWUPS.items():
        target = queue[queue["queue_event_id"].eq(queue_id)]
        error = ""; text = ""
        try:
            parts = dart_client.document_texts(receipt)
            text = _plain(parts)
            for index, part in enumerate(parts):
                name = re.sub(r"[^0-9A-Za-z._-]", "_", str(part.get("name", "document.xml")))
                (root / f"{receipt}_{index:02d}_{name}").write_text(str(part.get("text", "")), encoding="utf-8")
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
        if kind == "TRADING_HALT":
            # The KRX notice names only the listed issuer; its receipt date and
            # explicit halt/resumption fields link it to the decision disclosure.
            terms_ok = _contains(text, ("셀트리온",), ("매매거래정지",), ("중요내용공시",)) and _date_in(text, "2023", "08", "18")
            reason = "ADMINISTRATIVE_TRADING_HALT_LINKED_TO_ALREADY_RESOLVED_MERGER"
        elif kind == "REGISTRATION_STATEMENT":
            terms_ok = _contains(text, ("셀트리온헬스케어",), ("셀트리온",), ("0.4492620",), ("73,887,750", "73887750"))
            reason = "FOLLOWUP_DISCLOSURE_LINKED_TO_RESOLVED_ACQUIRER_NO_MARKET_FACTOR_MERGER"
        else:
            terms_ok = (_contains(text, ("셀트리온헬스케어",), ("셀트리온",), ("0.4492620",), ("73,887,750", "73887750"))
                        and _date_in(text, "2023", "12", "28") and _date_in(text, "2024", "01", "12"))
            reason = "FOLLOWUP_DISCLOSURE_LINKED_TO_RESOLVED_ACQUIRER_NO_MARKET_FACTOR_MERGER"
        ok = len(target) == 1 and core_ok and not error and terms_ok
        if len(target) != 1: failure = "UNIQUE_QUEUE_TARGET_UNAVAILABLE"
        elif not core_ok: failure = "PHASE591_CORE_RESOLUTION_MISMATCH"
        elif error: failure = "OPENDART_DOCUMENT_RETRIEVAL_FAILED"
        elif not terms_ok: failure = "FOLLOWUP_DOCUMENT_TERMS_MISMATCH"
        else: failure = reason
        if ok:
            evidence.append({"queue_event_id": queue_id,
                "verification_source": "OPENDART_MERGER_CHAIN_LINKAGE+PHASE591_CORE_RESOLUTION",
                "verification_reference": f"DART:{receipt}|DART:20230817000203|PHASE591:{CORE_QUEUE_ID}",
                "resolution_note": reason})
        audits.append({"queue_event_id": queue_id, "code": "068270", "rcept_no": receipt,
            "followup_type": kind, "phase591_core_valid": core_ok, "document_terms_valid": terms_ok,
            "verification_status": "NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED",
            "resolution_note": failure, "error": error})
    ep, ap, sp = Path(evidence_output_csv), Path(audit_output_csv), Path(summary_json)
    columns = ["queue_event_id", "verification_source", "verification_reference", "resolution_note"]
    pd.DataFrame(evidence, columns=columns).to_csv(ep, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap, index=False, encoding="utf-8-sig")
    summary = {"target_rows": len(FOLLOWUPS), "not_applicable_evidence_rows": len(evidence),
        "unresolved_rows": len(FOLLOWUPS) - len(evidence), "phase591_core_valid": core_ok,
        "documents_dir": str(root), "evidence_output_csv": str(ep), "audit_output_csv": str(ap)}
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
