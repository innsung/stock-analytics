from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

QUEUE_IDS={"939bbda40c4959a20bce","e28468435c8e4862e5e4"}
DOCS={
 "20211220800443":{"ratio":"1.0000000 : 0.0000000","shares":"0","terms":["CJ Schwan's Company Corp.","CJ Schwan's DE Corp.","발행주식총수 100%","신주를 발행하지 않는 무증자 합병"]},
 "20211220800458":{"ratio":"1.0000000 : 1.0000000","shares":"1680000","terms":["Schwan's Company","CJ Schwan's Company Corp.","발행주식총수 100%","보통주식 1,680,000"]},
}

def _plain(parts):
 raw=" ".join(str(x.get("text","")) for x in parts);return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))

def audit_cj_schwans_subsidiary_mergers_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");receipts=set(DOCS)
 qt=q[q.queue_event_id.isin(QUEUE_IDS)];dt=d[d.rcept_no.isin(receipts)];root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True)
 group_ok=len(qt)==2 and set(qt.queue_event_id)==QUEUE_IDS and len(dt)==2 and set(dt.rcept_no)==receipts;parent_rights=False;errors=[];validated=[]
 for receipt,spec in DOCS.items():
  try:
   parts=dart_client.document_texts(receipt);text=_plain(parts)
   for i,p in enumerate(parts):
    name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
   row=dt[dt.rcept_no.eq(receipt)];title=str(row.iloc[0].report_nm) if len(row)==1 else ""
   terms="회사합병결정" in title and "종속회사의주요경영사항" in title.replace(" ","") and "종속회사의 주요경영사항" in text and spec["ratio"] in text and all(x in text for x in spec["terms"])
   group_ok=group_ok and terms;parent_rights=parent_rights or "CJ제일제당 주주에게" in text or "CJ제일제당 주주배정" in text;validated.append({"receipt":receipt,"terms":terms})
  except Exception as exc:errors.append(f"{receipt}:{type(exc).__name__}:{exc}");group_ok=False
 ok=group_ok and not parent_rights and not errors
 if errors:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
 elif not group_ok:reason="SCHWANS_SUBSIDIARY_MERGER_GROUP_MISMATCH"
 elif parent_rights:reason="PARENT_HOLDER_RIGHTS_LANGUAGE_REQUIRES_REVIEW"
 else:reason="SCHWANS_INTERNAL_MERGERS_DO_NOT_CHANGE_CJ_CHEILJEDANG_HOLDER_UNITS"
 ref="|".join(f"DART:{r}" for r in sorted(receipts));evidence=[];audits=[]
 for qid in sorted(QUEUE_IDS):
  if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_CJ_SUBSIDIARY_MERGER_DATE_GROUP","verification_reference":ref,"resolution_note":reason})
  audits.append({"queue_event_id":qid,"code":"097950","group_receipts":"|".join(sorted(receipts)),"internal_merger_ratios":"1:0|1:1","internal_new_shares":"0|1680000","document_group_valid":group_ok,"parent_holder_rights_language":parent_rights,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":"|".join(errors)})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
 summary={"target_rows":2,"validated_documents":len(validated),"not_applicable_evidence_rows":len(evidence),"unresolved_rows":2-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
