from __future__ import annotations
import json,re
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

QID="cb08d9456cf27879002a";RECEIPT="20210630000881";TITLE="[기재정정]주요사항보고서(유상증자결정)"
def _last(soup,code):
 tags=soup.find_all(attrs={"acode":code});return tags[-1].get_text(" ",strip=True) if tags else ""
def audit_hd_ksoe_third_party_capital_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");qr=q[q.queue_event_id.eq(QID)];dr=d[d.rcept_no.eq(RECEIPT)];root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);error="";common=preferred=issue_price=None;participant=allotment=""
 try:
  parts=dart_client.document_texts(RECEIPT)
  for i,p in enumerate(parts):(root/f"{RECEIPT}_{i:02d}_{p.get('name','document.xml')}").write_text(str(p.get("text","")),encoding="utf-8")
  soup=BeautifulSoup(" ".join(str(p.get("text","")) for p in parts),"html.parser");common=int(re.sub(r"\D","",_last(soup,"CST_CNT")));preferred=int(re.sub(r"\D","",_last(soup,"PST_CNT")));issue_price=int(re.sub(r"\D","",_last(soup,"PST_ISS_VAL")));participant=_last(soup,"PART");allotment=_last(soup,"ALL_CNT")
 except Exception as exc:error=f"{type(exc).__name__}:{exc}"
 identity=len(qr)==1 and qr.iloc[0].code=="009540" and qr.iloc[0].source_reference_date=="20210630" and qr.iloc[0].source_description.strip()==TITLE
 disclosure=len(dr)==1 and dr.iloc[0].code=="009540" and dr.iloc[0].rcept_dt=="20210630" and dr.iloc[0].report_nm.strip()==TITLE and dr.iloc[0].flr_nm.strip()=="HD한국조선해양"
 terms=common==6099570 and preferred==9118231 and issue_price==137088 and bool(participant) and allotment.strip()=="-"
 ok=identity and disclosure and terms and not error;evidence=[]
 if not identity:reason="TARGET_QUEUE_IDENTITY_MISMATCH"
 elif not disclosure:reason="UNIQUE_OFFICIAL_DISCLOSURE_MISMATCH"
 elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
 elif not terms:reason="THIRD_PARTY_STRUCTURED_TERMS_MISMATCH"
 else:reason="THIRD_PARTY_CONVERTIBLE_PREFERRED_CAPITAL_RAISE_HAS_NO_EXISTING_HOLDER_RIGHT"
 if ok:evidence.append({"queue_event_id":QID,"verification_source":"OPENDART_STRUCTURED_THIRD_PARTY_CAPITAL_TERMS","verification_reference":f"DART:{RECEIPT}","resolution_note":reason})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);pd.DataFrame(evidence,columns=["queue_event_id","verification_source","verification_reference","resolution_note"]).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame([{"queue_event_id":QID,"code":"009540","rcept_no":RECEIPT,"common_shares":common,"preferred_shares":preferred,"preferred_issue_price":issue_price,"third_party_participant_present":bool(participant),"existing_holder_allotment":allotment,"queue_identity_valid":identity,"official_disclosure_valid":disclosure,"structured_terms_valid":terms,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":error}]).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":1,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":1-len(evidence),"evidence_output_csv":str(ep),"audit_output_csv":str(ap),"documents_dir":str(root),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
