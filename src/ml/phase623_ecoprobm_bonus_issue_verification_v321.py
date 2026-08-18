from __future__ import annotations
import json,re,sqlite3
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

QUEUE_ID="fe87e76e0b26e616df1c";DECISION="20220614000068";NOTICE="20220624900454"
def _value(soup,code):
 tags=soup.find_all(attrs={"acode":code});tag=tags[-1] if tags else None;return re.sub(r"[^0-9.]","",tag.get_text(" ",strip=True)) if tag else ""
def verify_ecoprobm_bonus_issue_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,trading_calendar_db:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");qr=q[q.queue_event_id.eq(QUEUE_ID)];notice=d[d.rcept_no.eq(NOTICE)];decision=d[d.rcept_no.eq(DECISION)];root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);error="";ratio=before=after=None
 try:
  parts=dart_client.document_texts(DECISION)
  for i,p in enumerate(parts):(root/f"{DECISION}_{i:02d}_{p.get('name','document.xml')}").write_text(str(p.get("text","")),encoding="utf-8")
  soup=BeautifulSoup(" ".join(str(p.get("text","")) for p in parts),"html.parser");ratio=float(_value(soup,"NEW_ASN_CST"));before=int(float(_value(soup,"BFR_CST_CNT")));after=int(float(_value(soup,"CST_CNT")))
 except Exception as exc:error=f"{type(exc).__name__}:{exc}"
 identity=len(qr)==1 and qr.iloc[0].code=="247540" and qr.iloc[0].source_reference_date=="20220624" and qr.iloc[0].source_description.strip()=="권리락(무상증자)"
 disclosures=len(notice)==1 and notice.iloc[0].code=="247540" and notice.iloc[0].rcept_dt=="20220624" and notice.iloc[0].report_nm.strip()=="권리락(무상증자)" and len(decision)==1 and decision.iloc[0].report_nm.strip()=="[기재정정]주요사항보고서(유무상증자결정)"
 dates=[]
 with sqlite3.connect(trading_calendar_db) as conn:dates=[str(x[0]) for x in conn.execute("select distinct date from stock_prices where code=? and date between ? and ? order by date",("247540","20220624","20220630"))]
 calendar_ok=dates[:2]==["20220624","20220627"]
 terms_ok=ratio==3.0 and before==24530810 and after==73351008
 ok=identity and disclosures and calendar_ok and terms_ok and not error;evidence=[];reason=""
 if not identity:reason="TARGET_QUEUE_IDENTITY_MISMATCH"
 elif not disclosures:reason="OFFICIAL_DECISION_OR_MARKET_NOTICE_MISMATCH"
 elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
 elif not terms_ok:reason="BONUS_ISSUE_STRUCTURED_TERMS_MISMATCH"
 elif not calendar_ok:reason="OFFICIAL_EX_RIGHTS_TRADING_BOUNDARY_MISMATCH"
 else:
  reason="BONUS_FACTOR_CONFIRMED_BY_DART_ALLOTMENT_AND_OFFICIAL_EX_RIGHTS_BOUNDARY";evidence.append({"queue_event_id":QUEUE_ID,"code":"247540","event_family":"CORPORATE_ACTION","source_reference_date":"20220624","effective_date":"20220627","known_at":"20220614","action_type":"BONUS","adjustment_factor":4.0,"cash_amount":0.0,"verification_source":"OPENDART_STRUCTURED_BONUS_TERMS+KRX_OFFICIAL_EX_RIGHTS_NOTICE+LOCAL_TRADING_CALENDAR","verification_reference":f"DART:{DECISION}|KRX_DART:{NOTICE}","resolution_note":reason})
 cols=["queue_event_id","code","event_family","source_reference_date","effective_date","known_at","action_type","adjustment_factor","cash_amount","verification_source","verification_reference","resolution_note"];ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame([{"queue_event_id":QUEUE_ID,"decision_rcept_no":DECISION,"notice_rcept_no":NOTICE,"allotment_ratio":ratio,"before_shares":before,"after_shares":after,"effective_date":"20220627" if calendar_ok else "","adjustment_factor":4.0 if terms_ok else "","queue_identity_valid":identity,"official_disclosures_valid":disclosures,"trading_calendar_valid":calendar_ok,"verification_status":"STRICT_BONUS_EVIDENCE_READY" if ok else "UNRESOLVED","reason":reason,"error":error}]).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":1,"strict_evidence_rows":len(evidence),"effective_date":"20220627" if ok else "","adjustment_factor":4.0 if ok else None,"evidence_output_csv":str(ep),"audit_output_csv":str(ap),"documents_dir":str(root),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
