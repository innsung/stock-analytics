from __future__ import annotations
import json,re
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

QID="6bc7eafe43bf25efd8f1";BASE="20201113001192";FINAL="20201208000431";ATTACH="20201123000205"
def _last(soup,code):
 tags=soup.find_all(attrs={"acode":code});return tags[-1].get_text(" ",strip=True) if tags else ""
def audit_shinhan_neoplux_share_exchange_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,phase621_audit_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");p=pd.read_csv(phase621_audit_csv,dtype=str).fillna("");qr=q[q.queue_event_id.eq(QID)];root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);error="";target_shares=None;ratio=effect=manager=""
 try:
  parts=dart_client.document_texts(FINAL)
  for i,x in enumerate(parts):(root/f"{FINAL}_{i:02d}_{x.get('name','document.xml')}").write_text(str(x.get("text","")),encoding="utf-8")
  soup=BeautifulSoup(" ".join(str(x.get("text","")) for x in parts),"html.parser");target_shares=int(re.sub(r"\D","",_last(soup,"EXCH_CST_CNT")));ratio=_last(soup,"EXCH_RT");effect=_last(soup,"EXCH_EFT");manager=_last(soup,"MGR_STO")
 except Exception as exc:error=f"{type(exc).__name__}:{exc}"
 base=d[d.rcept_no.eq(BASE)];final=d[d.rcept_no.eq(FINAL)];chain=p[p.queue_event_id.eq("9c9b83fcf9dc64c75fa2")]
 identity=len(qr)==1 and qr.iloc[0].code=="055550" and qr.iloc[0].source_reference_date=="20201113" and qr.iloc[0].source_description.strip()=="주요사항보고서(주식교환ㆍ이전결정)"
 disclosures=len(base)==1 and base.iloc[0].report_nm.strip()=="주요사항보고서(주식교환ㆍ이전결정)" and len(final)==1 and final.iloc[0].report_nm.strip()=="[기재정정]주요사항보고서(주식교환ㆍ이전결정)"
 amendment=len(chain)==1 and chain.iloc[0].child_rcept_no==ATTACH and chain.iloc[0].parent_rcept_no==BASE and chain.iloc[0].resolved_anchor_valid=="True" and chain.iloc[0].verification_status=="NOT_APPLICABLE_EVIDENCE"
 terms=target_shares==25227445 and "0.0893119" in ratio and "0.02%" in effect and bool(manager)
 ok=identity and disclosures and amendment and terms and not error
 if not identity:reason="TARGET_QUEUE_IDENTITY_MISMATCH"
 elif not disclosures:reason="BASE_OR_FINAL_DISCLOSURE_MISMATCH"
 elif not amendment:reason="PHASE621_AMENDMENT_CHAIN_MISMATCH"
 elif error:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
 elif not terms:reason="SHARE_EXCHANGE_STRUCTURED_TERMS_MISMATCH"
 else:reason="SMALL_SCALE_SUBSIDIARY_SHARE_EXCHANGE_ADDS_NO_EXISTING_HOLDER_DISTRIBUTION"
 evidence=[]
 if ok:evidence.append({"queue_event_id":QID,"verification_source":"OPENDART_FINAL_SHARE_EXCHANGE_TERMS+PHASE621_AMENDMENT_CHAIN","verification_reference":f"DART:{BASE}|DART:{FINAL}|PHASE621:{ATTACH}","resolution_note":reason})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);pd.DataFrame(evidence,columns=["queue_event_id","verification_source","verification_reference","resolution_note"]).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame([{"queue_event_id":QID,"code":"055550","base_rcept_no":BASE,"final_rcept_no":FINAL,"exchange_target_shares":target_shares,"exchange_ratio_contains_0_0893119":"0.0893119" in ratio,"existing_holder_change_below_0_02pct":"0.02%" in effect,"small_scale_no_appraisal_terms_present":bool(manager),"queue_identity_valid":identity,"official_disclosures_valid":disclosures,"phase621_amendment_chain_valid":amendment,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":error}]).to_csv(ap,index=False,encoding="utf-8-sig");summary={"target_rows":1,"not_applicable_evidence_rows":len(evidence),"unresolved_rows":1-len(evidence),"evidence_output_csv":str(ep),"audit_output_csv":str(ap),"documents_dir":str(root),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
