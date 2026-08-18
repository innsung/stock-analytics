from __future__ import annotations
import html,json,re
from pathlib import Path
import pandas as pd

GROUPS={
 "010140":({"82f9403868eaca220298","def855d6dbe32557bfea","ff7ee0baca220ee2d5bf"},{"20211028000442","20211028000444","20211028000447"},"250,000,000",{"삼성전자","삼성생명","삼성전기"}),
 "207940":({"a0b793cd3bb548dfcca5","404825dba0edd7e5b724"},{"20220329000816","20220329000827"},"5,009,000",{"삼성물산","삼성전자"}),
}
EXPECTED_PARTICIPANT={"20211028000442":"삼성전자","20211028000444":"삼성생명","20211028000447":"삼성전기","20220329000816":"삼성물산","20220329000827":"삼성전자"}
def _plain(parts):
 raw=" ".join(str(x.get("text","")) for x in parts);return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))
def audit_related_party_rights_participation_v321(dart_client,*,actionable_queue_csv:str,disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
 q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("");root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);evidence=[];audits=[]
 for code,(qids,receipts,offering_shares,participants) in GROUPS.items():
  qt=q[q.queue_event_id.isin(qids)];dt=d[d.rcept_no.isin(receipts)];valid=len(qt)==len(qids) and set(qt.queue_event_id)==qids and len(dt)==len(receipts) and set(dt.rcept_no)==receipts;found=set();errors=[]
  for receipt in sorted(receipts):
   try:
    parts=dart_client.document_texts(receipt);text=_plain(parts)
    for i,p in enumerate(parts):
     name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")));(root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
    row=dt[dt.rcept_no.eq(receipt)];title=str(row.iloc[0].report_nm) if len(row)==1 else "";expected=EXPECTED_PARTICIPANT[receipt]
    participant_field=bool(re.search(rf"유상증자 참여자\s+{re.escape(expected)}(?:\(주\))?\s+회사와의 관계",text));found.add(expected) if participant_field else None
    terms="특수관계인의유상증자참여" in title.replace(" ","") and "특수관계인의 유상증자 참여" in text and participant_field and "출자주식수" in text and offering_shares in text
    valid=valid and terms
   except Exception as exc:errors.append(f"{receipt}:{type(exc).__name__}:{exc}");valid=False
  valid=valid and found==participants;ok=valid and not errors
  if errors:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
  elif not valid:reason="RELATED_PARTY_PARTICIPATION_GROUP_MISMATCH"
  else:reason="PARTICIPATION_NOTICE_DUPLICATES_UNDERLYING_RIGHTS_OFFERING_AND_ADDS_NO_RETURN_EVENT"
  ref="|".join(f"DART:{r}" for r in sorted(receipts))
  for qid in sorted(qids):
   if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_RELATED_PARTY_RIGHTS_PARTICIPATION_GROUP","verification_reference":ref,"resolution_note":reason})
   audits.append({"queue_event_id":qid,"code":code,"group_receipts":"|".join(sorted(receipts)),"participants":"|".join(sorted(found)),"underlying_offering_shares":offering_shares.replace(",",""),"underlying_offering_still_independently_audited":True,"document_group_valid":valid,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":"|".join(errors)})
 ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
 pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig");total=sum(len(x[0]) for x in GROUPS.values())
 summary={"target_rows":total,"issuer_groups":len(GROUPS),"not_applicable_evidence_rows":len(evidence),"unresolved_rows":total-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
