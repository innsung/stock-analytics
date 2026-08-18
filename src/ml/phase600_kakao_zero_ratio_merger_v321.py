from __future__ import annotations
import html, json, re
from pathlib import Path
import pandas as pd
from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321

QUEUE_ID="03f28f1f0e6e787d420a"; RECEIPT="20240503000787"

def _plain(parts):
    raw=" ".join(str(x.get("text","")) for x in parts)
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))

def audit_kakao_zero_ratio_merger_v321(dart_client,provider,*,actionable_queue_csv:str,documents_dir:str,
    evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
    q=pd.read_csv(actionable_queue_csv,dtype=str).fillna(""); target=q[q["queue_event_id"].eq(QUEUE_ID)]
    root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);error="";text=""
    try:
        parts=dart_client.document_texts(RECEIPT);text=_plain(parts)
        for i,p in enumerate(parts):
            name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")))
            (root/f"{RECEIPT}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
    except Exception as exc:error=f"{type(exc).__name__}:{exc}"
    terms=all(x in text for x in ("카카오스페이스","지분을 100%","합병비율은 1:0","합병신주를 발행하지 않는","별도의 합병교부금도 없습니다"))
    bp=detect_adjustment_breakpoints_v321(provider,code="035720",center_date="20240501",window_days=12)
    ok=len(target)==1 and not error and terms and bp.empty
    if len(target)!=1:reason="UNIQUE_QUEUE_TARGET_UNAVAILABLE"
    elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
    elif not terms:reason="ZERO_RATIO_MERGER_COMPLETION_TERMS_MISMATCH"
    elif not bp.empty:reason="KRX_MERGER_BREAKPOINT_REQUIRES_REVIEW"
    else:reason="WHOLLY_OWNED_ZERO_RATIO_MERGER_HAS_NO_SHARE_OR_CASH_CONSIDERATION"
    evidence=[]
    if ok:evidence=[{"queue_event_id":QUEUE_ID,"verification_source":"OPENDART_MERGER_COMPLETION+KRX_NO_BREAKPOINT","verification_reference":f"DART:{RECEIPT}","resolution_note":reason}]
    ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
    pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig")
    pd.DataFrame([{"queue_event_id":QUEUE_ID,"code":"035720","rcept_no":RECEIPT,"absorbed_company":"Kakao Space","merger_date":"20240501","merger_ratio":"1:0","new_shares":0,"cash_consideration":0,"krx_adjustment_breakpoints":len(bp),"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":error}]).to_csv(ap,index=False,encoding="utf-8-sig")
    summary={"target_rows":1,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":1-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)}
    sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
