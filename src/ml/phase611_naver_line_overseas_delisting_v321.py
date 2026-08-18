from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd
from src.ml.market_effective_date_v321 import detect_adjustment_breakpoints_v321

TARGETS={"e246615dbf42b9bae35b":"20201109800500","e858e7bb598f98411b5a":"20201228800756"}
EFFECTIVE_DATE="20201229"
def _plain(parts):
 raw=" ".join(str(x.get("text","")) for x in parts);return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))
def _date(text):return bool(re.search(r"2020\D{0,20}12\D{0,20}29",text))

def audit_naver_line_overseas_delisting_v321(dart_client,provider,*,actionable_queue_csv:str,disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True)
 try:bp=detect_adjustment_breakpoints_v321(provider,code="035420",center_date=EFFECTIVE_DATE,window_days=12);market_error=""
 except Exception as exc:bp=pd.DataFrame();market_error=f"{type(exc).__name__}:{exc}"
 evidence=[];audits=[]
 for qid,receipt in TARGETS.items():
  qt=q[q.queue_event_id.eq(qid)];dt=d[d.rcept_no.eq(receipt)];error="";terms=False
  try:
   parts=dart_client.document_texts(receipt) if len(qt)==len(dt)==1 else [];text=_plain(parts)
   for i,p in enumerate(parts):
    name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
   title=str(dt.iloc[0].report_nm) if len(dt)==1 else ""
   terms="해외증권시장" in title and "상장폐지" in title and "종속회사의주요경영사항" in title.replace(" ","") and all(x in text for x in ("종속회사의 주요경영사항","LINE Corporation","상장폐지","동경증권거래소","뉴욕증권거래소","243,715,542")) and _date(text)
  except Exception as exc:error=f"{type(exc).__name__}:{exc}"
  ok=len(qt)==len(dt)==1 and terms and not error and not market_error and bp.empty
  if len(qt)!=1 or len(dt)!=1:reason="TARGET_OR_UNIQUE_DISCLOSURE_UNAVAILABLE"
  elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
  elif not terms:reason="LINE_OVERSEAS_DELISTING_TERMS_UNCONFIRMED"
  elif market_error:reason="NAVER_KRX_RETRIEVAL_FAILED"
  elif not bp.empty:reason="NAVER_DOMESTIC_ADJUSTMENT_BREAKPOINT_REQUIRES_REVIEW"
  else:reason="LINE_OVERSEAS_DELISTING_DOES_NOT_CHANGE_NAVER_LISTED_HOLDER_UNITS"
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_LINE_OVERSEAS_DELISTING+KRX_NAVER_NO_BREAKPOINT","verification_reference":f"DART:{receipt}|DART:20201109800500|DART:20201228800756","resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":"035420","rcept_no":receipt,"subsidiary":"LINE Corporation","venues":"Tokyo Stock Exchange|New York Stock Exchange","delisted_shares":"243715542","overseas_delisting_date":EFFECTIVE_DATE,"document_terms_confirmed":terms,"naver_krx_breakpoints":len(bp),"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":error or market_error})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
 summary={"target_rows":2,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":2-len(evidence),"naver_krx_breakpoints":len(bp),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
