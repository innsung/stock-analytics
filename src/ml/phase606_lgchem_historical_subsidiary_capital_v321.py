from __future__ import annotations

import html, json, re
from pathlib import Path
import pandas as pd

GROUPS = {
    "20210416": ({"f08820bee6b5165bbc5b", "a825567055af9390b708"}, {"20210416800729", "20210416800738"}),
    "20220125": ({"adf8e22925cf1e6849c0", "396f3d5c117295f78692"}, {"20220125800706", "20220125800717"}),
    "20221012": ({"97237c6bf559415f526b"}, {"20221012800588"}),
}

def _plain(parts):
    raw=" ".join(str(x.get("text","")) for x in parts)
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",raw)))

def audit_lgchem_historical_subsidiary_capital_v321(dart_client,*,actionable_queue_csv:str,
    disclosures_csv:str,documents_dir:str,evidence_output_csv:str,audit_output_csv:str,summary_json:str)->dict:
    q=pd.read_csv(actionable_queue_csv,dtype=str).fillna("");d=pd.read_csv(disclosures_csv,dtype=str).fillna("")
    root=Path(documents_dir);root.mkdir(parents=True,exist_ok=True);evidence=[];audits=[]
    for date,(qids,receipts) in GROUPS.items():
        qt=q[q.queue_event_id.isin(qids)];dt=d[d.rcept_no.isin(receipts)]
        group_ok=len(qt)==len(qids) and set(qt.queue_event_id)==qids and len(dt)==len(receipts) and set(dt.rcept_no)==receipts
        parent_rights=False;errors=[];subsidiaries=[]
        for receipt in sorted(receipts):
            try:
                parts=dart_client.document_texts(receipt);text=_plain(parts)
                for i,p in enumerate(parts):
                    name=re.sub(r"[^0-9A-Za-z._-]","_",str(p.get("name","document.xml")))
                    (root/f"{receipt}_{i:02d}_{name}").write_text(str(p.get("text","")),encoding="utf-8")
                title_rows=dt[dt.rcept_no.eq(receipt)];title=str(title_rows.iloc[0].report_nm) if len(title_rows)==1 else ""
                terms="유상증자결정" in title and "종속회사의주요경영사항" in title.replace(" ","") and all(x in text for x in ("유상증자결정","종속회사의 주요경영사항","종속회사인","신주의 종류와 수"))
                group_ok=group_ok and terms
                parent_rights=parent_rights or "LG화학 주주에게 신주" in text or "LG화학 주주배정" in text
                for name in ("LG Energy Solution Michigan, Inc.","LG Energy Solution Michigan Inc.","Ultium Cells LLC"):
                    if name in text:subsidaries_name=name;subsidiaries.append(subsidaries_name)
            except Exception as exc:errors.append(f"{receipt}:{type(exc).__name__}:{exc}");group_ok=False
        ok=group_ok and not parent_rights and not errors
        if errors:reason="OPENDART_DOCUMENT_RETRIEVAL_FAILED"
        elif not group_ok:reason="SUBSIDIARY_CAPITAL_INCREASE_GROUP_MISMATCH"
        elif parent_rights:reason="PARENT_HOLDER_RIGHTS_LANGUAGE_REQUIRES_REVIEW"
        else:reason="SUBSIDIARY_CAPITAL_INCREASE_DOES_NOT_CHANGE_LGCHEM_HOLDER_UNITS"
        ref="|".join(f"DART:{r}" for r in sorted(receipts))
        for qid in sorted(qids):
            if ok:evidence.append({"queue_event_id":qid,"verification_source":"OPENDART_LGCHEM_SUBSIDIARY_CAPITAL_DATE_GROUP","verification_reference":ref,"resolution_note":reason})
            audits.append({"queue_event_id":qid,"code":"051910","disclosure_date":date,"group_receipts":"|".join(sorted(receipts)),"subsidiaries":"|".join(sorted(set(subsidiaries))),"document_group_valid":group_ok,"parent_holder_rights_language":parent_rights,"verification_status":"NOT_APPLICABLE_EVIDENCE" if ok else "UNRESOLVED","resolution_note":reason,"error":"|".join(errors)})
    ep,ap,sp=Path(evidence_output_csv),Path(audit_output_csv),Path(summary_json);cols=["queue_event_id","verification_source","verification_reference","resolution_note"]
    pd.DataFrame(evidence,columns=cols).to_csv(ep,index=False,encoding="utf-8-sig");pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
    total=sum(len(x) for x,_ in GROUPS.values());summary={"target_rows":total,"date_groups":len(GROUPS),"not_applicable_evidence_rows":len(evidence),"unresolved_rows":total-len(evidence),"documents_dir":str(root),"evidence_output_csv":str(ep),"audit_output_csv":str(ap)}
    sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");return summary|{"summary_json":str(sp)}
