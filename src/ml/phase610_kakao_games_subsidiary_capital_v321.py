from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

QUEUE_IDS={"4d89be4efa9fad94ecb1","2d7bb95f4042d7eba7c0","a8674f07b6a7a1523ef1"}
DOCS={
 "20211101800199":("KAKAO_GAMES_EUROPE","328,759,918"),
 "20211101800204":("KAKAO_GAMES","2,711,805"),
 "20211112800924":("KAKAO_GAMES_EUROPE","328,759,918"),
}

def _plain(parts):
 raw=" ".join(str(x.get("text","")) for x in parts);return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))

def audit_kakao_games_subsidiary_capital_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");receipts=set(DOCS)
 qt=q[q.queue_event_id.isin(QUEUE_IDS)];dt=d[d.rcept_no.isin(receipts)];root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True)
 group_ok=len(qt)==3 and set(qt.queue_event_id)==QUEUE_IDS and len(dt)==3 and set(dt.rcept_no)==receipts;parent_rights=False;errors=[];validated=[]
 for receipt,(issuer,shares) in DOCS.items():
  try:
   parts=dart_client.document_texts(receipt);text=_plain(parts)
   for i,p in enumerate(parts):
    name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
   row=dt[dt.rcept_no.eq(receipt)];title=str(row.iloc[0].report_nm) if len(row)==1 else ""
   issuer_ok="Kakao Games Europe B.V." in text if issuer=="KAKAO_GAMES_EUROPE" else "카카오게임즈" in text and "Kakao Games Europe B.V." not in text
   terms="유상증자결정" in title and "종속회사의주요경영사항" in title.replace(" ","") and all(x in text for x in ("종속회사의 주요경영사항","종속회사인","신주의 종류와 수",shares)) and issuer_ok
   group_ok=group_ok and terms;parent_rights=parent_rights or "카카오 주주에게 신주" in text or "카카오 주주배정" in text;validated.append({"receipt":receipt,"issuer":issuer,"shares":shares,"valid":terms})
  except Exception as exc:errors.append(f"{receipt}:{type(exc).__name__}:{exc}");group_ok=False
 ok=group_ok and not parent_rights and not errors
 if errors:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
 elif not group_ok:reason="KAKAO_GAMES_SUBSIDIARY_CAPITAL_CHAIN_MISMATCH"
 elif parent_rights:reason="PARENT_HOLDER_RIGHTS_LANGUAGE_REQUIRES_REVIEW"
 else:reason="KAKAO_GAMES_SUBSIDIARY_CAPITAL_DOES_NOT_CHANGE_KAKAO_HOLDER_UNITS"
 ref="|".join(f"DART:{r}" for r in sorted(receipts));evidence=[];audits=[]
 for qid in sorted(QUEUE_IDS):
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_KAKAO_GAMES_SUBSIDIARY_CAPITAL_CHAIN","verification_reference":ref,"resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":"035720","chain_receipts":"|".join(sorted(receipts)),"subsidiary_issuances":"KAKAO_GAMES:2711805|KAKAO_GAMES_EUROPE:328759918","document_chain_valid":group_ok,"parent_holder_rights_language":parent_rights,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":"|".join(errors)})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
 summary={"target_rows":3,"validated_documents":len(validated),"not_applicable_evidence_rows":len(evidence),"unresolved_rows":3-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
