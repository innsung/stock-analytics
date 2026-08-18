from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd


FOLLOWUP_RECEIPTS = {
    "bab7182c1ebff1c4f9e0": "20260504800387",
    "de4a350cccca019bc0cc": "20250530800569",
    "22ce2ade3540019df009": "20250530002559",
    "bcc2ff9b25645c8d8da8": "20250529800027",
    "cec6598232cfffeb0da1": "20250523800036",
    "15d73058dbca800917d0": "20250522800003",
}


def _plain(parts: list[dict[str, str]]) -> str:
    raw=" ".join(part["text"] for part in parts)
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))


def resolve_recent_followups_v321(
    dart_client, *, actionable_queue_csv: str, resolved_verification_csv: str,
    documents_dir: str, evidence_output_csv: str, audit_output_csv: str,
) -> dict:
    queue=pd.read_csv(actionable_queue_csv,dtype=str).fillna("")
    resolved=pd.read_csv(resolved_verification_csv,dtype=str).fillna("")
    targets=queue[queue["workstream"].eq("P4_RECENT_FOLLOWUP_REVIEW")]
    root=Path(documents_dir); root.mkdir(parents=True,exist_ok=True)
    evidence=[]; audits=[]
    for target in targets.itertuples(index=False):
        receipt=FOLLOWUP_RECEIPTS.get(target.queue_event_id,"")
        status="UNRESOLVED"; reason=""; parent_reference=""
        try:
            parts=dart_client.document_texts(receipt) if receipt else []
            text=_plain(parts)
            for index,part in enumerate(parts):
                (root/f"{receipt}_{index:02d}_{part['name']}").write_text(part["text"],encoding="utf-8")
            code=str(target.code).zfill(6)
            if code=="006400" and "유상증자" in text and (
                "청약결과" in text or "발행결과" in text) and "2025-05-19 유상증자결정" in text:
                parent=resolved[(resolved["code"].eq(code)) & resolved["action_type"].eq("RIGHTS") &
                                resolved["resolution_status"].eq("VERIFIED")]
                if len(parent)==1:
                    status="EXPLICIT_FOLLOWUP_NOT_INDEPENDENT_EVENT"; reason="RIGHTS_SUBSCRIPTION_OR_ISSUANCE_RESULT_LINKED_TO_VERIFIED_PRIMARY"
                    parent_reference=parent.iloc[0]["verification_reference"]
            elif code=="267250" and "합병비율" in text and "1 : 0" in text and "신주를 발행하지 않" in text and "교부금도 없" in text:
                status="EXPLICIT_FOLLOWUP_NOT_INDEPENDENT_EVENT"; reason="MERGER_COMPLETION_CONFIRMS_NO_NEW_SHARES_OR_CASH_CONSIDERATION"
                parent_reference="DART:20250425000887"
            elif code=="207940" and "매매거래정지" in text and "회사분할 결정" in text and "2025-05-22 07:45" in text and "2025-05-22 09:30" in text:
                status="EXPLICIT_MARKET_ADMINISTRATION_NOT_ADJUSTMENT_EVENT"; reason="INTRADAY_SUSPENSION_REQUIRES_SEPARATE_SUSPENSION_DATA_NOT_CORPORATE_ACTION_FACTOR"
                parent_reference="DART:20250522000001"
            elif code=="009540" and "교환사채 발행" in text and "납입완료" in text and "2026-04-01 교환사채권발행결정" in text:
                status="EXPLICIT_FOLLOWUP_NOT_INDEPENDENT_EVENT"; reason="EXCHANGEABLE_BOND_PAYMENT_COMPLETION_LINKED_TO_PRIMARY_DECISION"
                parent_reference="DART:20260401002847"
        except Exception as exc:
            reason=f"{type(exc).__name__}: {exc}"
        valid=status.startswith("EXPLICIT_")
        reference="|".join(x for x in [f"DART:{receipt}" if receipt else "",parent_reference] if x)
        if valid:
            evidence.append({"queue_event_id":target.queue_event_id,
                "verification_source":"OPENDART_FOLLOWUP_SEMANTIC_LINK",
                "verification_reference":reference,"resolution_note":reason})
        audits.append({"queue_event_id":target.queue_event_id,"code":str(target.code).zfill(6),
            "rcept_no":receipt,"semantic_status":status,"parent_reference":parent_reference,
            "reason":reason,"promotion_status":"NOT_APPLICABLE_EVIDENCE" if valid else "NOT_PROMOTED"})
    ep,ap=Path(evidence_output_csv),Path(audit_output_csv)
    pd.DataFrame(evidence,columns=["queue_event_id","verification_source","verification_reference","resolution_note"]).to_csv(ep,index=False,encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
    return {"target_rows":len(targets),"not_applicable_evidence_rows":len(evidence),
            "unresolved_rows":len(targets)-len(evidence),"evidence_output_csv":str(ep),
            "audit_output_csv":str(ap),"documents_dir":str(root)}
