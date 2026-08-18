from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

TARGETS={
 "5280233dfd2abc7060cb":("000660","20201020800057",("영업양수도",)),
 "df8754dd81581aade524":("068270","20200611800559",("영업양수도",)),
 "b1ca446afd55114b5f60":("247540","20200203900304",("단일판매공급계약","단일판매ㆍ공급계약")),
 "eb1d77b99854bfb33838":("042700","20200122800114",("주식소각",)),
}
def _plain(parts):
 raw=" ".join(str(x.get("text","")) for x in parts);return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))
def audit_historical_administrative_trading_halts_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);evidence=[];audits=[]
 for qid,(code,receipt,reasons) in TARGETS.items():
  qt=q[q.queue_event_id.eq(qid)];dt=d[d.rcept_no.eq(receipt)];error="";terms=False;matched=""
  try:
   parts=dart_client.document_texts(receipt) if len(qt)==len(dt)==1 else [];text=_plain(parts)
   for i,p in enumerate(parts):
    name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
   title=str(dt.iloc[0].report_nm) if len(dt)==1 else "";matched=next((x for x in reasons if x in text),"")
   terms="매매거래정지" in text and bool(matched) and ("매매거래정지" in title or "주권매매거래정지" in title)
  except Exception as exc:error=f"{type(exc).__name__}:{exc}"
  ok=len(qt)==len(dt)==1 and terms and not error
  if len(qt)!=1 or len(dt)!=1:reason="TARGET_OR_UNIQUE_KRX_DISCLOSURE_UNAVAILABLE"
  elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
  elif not terms:reason="TRADING_HALT_ADMINISTRATIVE_TERMS_UNCONFIRMED"
  else:reason="ADMINISTRATIVE_TRADING_HALT_IS_NOT_AN_ADDITIONAL_SHAREHOLDER_RETURN_EVENT"
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"KRX_ADMINISTRATIVE_TRADING_HALT_PRIMARY_DOCUMENT","verification_reference":f"DART:{receipt}","resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":code,"rcept_no":receipt,"halt_reason":matched,"document_terms_confirmed":terms,"share_or_cash_terms_applied":False,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":error})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
 summary={"target_rows":len(TARGETS),"not_applicable_evidence_rows":len(evidence),"unresolved_rows":len(TARGETS)-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
