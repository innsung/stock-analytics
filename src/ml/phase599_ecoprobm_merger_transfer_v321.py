from __future__ import annotations

import html, json, re
from pathlib import Path
import pandas as pd

from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321

MERGER_IDS = {"6684ffeaa6e0f5358f4b", "9425dbaa6796b905188a"}
TRANSFER_ID = "0caa1e190a1b397dcee0"
DECISION, COMPLETION, TRANSFER = "20240326000614", "20240603000252", "20240227900523"


def _plain(parts):
    raw = " ".join(str(x.get("text", "")) for x in parts)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def audit_ecoprobm_merger_transfer_v321(dart_client, provider, *, actionable_queue_csv: str,
    documents_dir: str, evidence_output_csv: str, audit_output_csv: str, summary_json: str) -> dict:
    q = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    texts, errors = {}, []
    for receipt in (DECISION, COMPLETION, TRANSFER):
        try:
            parts = dart_client.document_texts(receipt); texts[receipt] = _plain(parts)
            for i, part in enumerate(parts):
                name = re.sub(r"[^0-9A-Za-z._-]", "_", str(part.get("name", "document.xml")))
                (root/f"{receipt}_{i:02d}_{name}").write_text(str(part.get("text", "")), encoding="utf-8")
        except Exception as exc: errors.append(f"{receipt}:{type(exc).__name__}:{exc}")
    decision, completion, transfer = texts.get(DECISION,""), texts.get(COMPLETION,""), texts.get(TRANSFER,"")
    merger_ok = all(x in decision for x in ("에코프로글로벌", "지분 100%", "1 : 0.0000000", "합병 신주를 발행하지 않는"))
    completion_ok = all(x in completion for x in ("합병기일 2024.05.30", "합병비율은 1: 0", "신주를 발행하지 않습니다"))
    transfer_ok = all(x in transfer for x in ("상장폐지승인을위한의안상정결정", "유가증권시장상장", "코스닥시장 상장폐지"))
    bp = detect_adjustment_breakpoints_v321(provider, code="247540", center_date="20240530", window_days=12)
    evidence, audits = [], []
    for queue_id in sorted(MERGER_IDS | {TRANSFER_ID}):
        unique = len(q[q["queue_event_id"].eq(queue_id)]) == 1
        ok = transfer_ok if queue_id == TRANSFER_ID else merger_ok and completion_ok and bp.empty
        status = "NOT_APPLICABLE_EVIDENCE" if unique and ok and not errors else "UNRESOLVED"
        if not unique: reason = "UNIQUE_QUEUE_TARGET_UNAVAILABLE"
        elif errors: reason = "OPENDART_DOCUMENT_RETRIEVAL_FAILED"
        elif queue_id in MERGER_IDS and not bp.empty: reason = "KRX_MERGER_BREAKPOINT_REQUIRES_REVIEW"
        elif not ok: reason = "LEGAL_EVENT_TERMS_MISMATCH"
        elif queue_id == TRANSFER_ID: reason = "MARKET_TRANSFER_PROPOSAL_DOES_NOT_CHANGE_SHAREHOLDER_UNITS_OR_CASH"
        else: reason = "WHOLLY_OWNED_ZERO_RATIO_MERGER_DOES_NOT_CHANGE_LISTED_HOLDER_UNITS"
        receipt_ref = f"DART:{TRANSFER}" if queue_id == TRANSFER_ID else f"DART:{DECISION}|DART:{COMPLETION}"
        if status == "NOT_APPLICABLE_EVIDENCE": evidence.append({"queue_event_id":queue_id,
            "verification_source":"OPENDART_PRIMARY_LEGAL_EVENT+KRX_APPLICABILITY_CHECK",
            "verification_reference":receipt_ref,"resolution_note":reason})
        audits.append({"queue_event_id":queue_id,"code":"247540","event_type":"MARKET_TRANSFER" if queue_id==TRANSFER_ID else "ZERO_RATIO_MERGER",
            "decision_rcept_no":TRANSFER if queue_id==TRANSFER_ID else DECISION,"completion_rcept_no":"" if queue_id==TRANSFER_ID else COMPLETION,
            "krx_adjustment_breakpoints":"" if queue_id==TRANSFER_ID else len(bp),"verification_status":status,"resolution_note":reason,"errors":"|".join(errors)})
    ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json)
    cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
    pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
    summary={"target_rows":3,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":3-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)}
    sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
