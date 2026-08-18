from __future__ import annotations
import hashlib,json,tempfile,zipfile
from pathlib import Path
import pandas as pd

def _sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def verify_release_restore_drill_v321(*,release_zip:str,manifest_csv:str,audit_output_csv:str,summary_json:str)->dict:
 manifest=pd.read_csv(manifest_csv,dtype=str).fillna("");rows=[];restored_entries=0
 with tempfile.TemporaryDirectory(prefix="stock_analytics_release_restore_") as temp:
  root=Path(temp).resolve()
  with zipfile.ZipFile(release_zip) as z:
   members=z.infolist();safe=all((root/m.filename).resolve().is_relative_to(root) for m in members);rows.append({"check":"ZIP_PATH_SAFETY","target":release_zip,"status":"PASS" if safe else "FAIL","detail":f"entries={len(members)}"})
   if not safe:raise ValueError("unsafe path found in release ZIP")
   z.extractall(root);restored_entries=len(members)
  restored={p.name:p for p in root.rglob("*") if p.is_file()}
  for _,r in manifest.iterrows():
   name=Path(r["path"]).name;p=restored.get(name);exists=p is not None;size=p.stat().st_size if exists else -1;digest=_sha(p) if exists else "";ok=exists and size==int(r["size_bytes"]) and digest.lower()==r["sha256"].lower();rows.append({"check":"RESTORED_MANIFEST_FILE","target":name,"status":"PASS" if ok else "FAIL","detail":f"exists={exists};size={size};sha256={digest}"})
  ledger=restored.get("event_verification_resolved_phase625_v321.csv");actionable=restored.get("actionable_resolution_queue_phase625_v321.csv");semantic=False
  if ledger and actionable:
   lv=pd.read_csv(ledger,dtype=str).fillna("");av=pd.read_csv(actionable,dtype=str).fillna("");semantic=len(lv)==399 and lv.queue_event_id.nunique()==399 and len(av)==0
  rows.append({"check":"RESTORED_SEMANTIC_SMOKE","target":"canonical ledger + actionable queue","status":"PASS" if semantic else "FAIL","detail":"ledger_rows=399;unique_ids=399;actionable_rows=0"})
 audit=pd.DataFrame(rows);passed=audit.status.eq("PASS").all();ap,sp=Path(audit_output_csv),Path(summary_json);ap.parent.mkdir(parents=True,exist_ok=True);audit.to_csv(ap,index=False,encoding="utf-8-sig");summary={"phase":"V3.2.1 Phase 6.28","restore_drill":"PASS" if passed else "FAIL","checks_total":len(audit),"checks_passed":int(audit.status.eq("PASS").sum()),"restored_entries":restored_entries,"manifest_files":len(manifest),"temporary_restore_cleaned":True,"audit_output_csv":str(ap),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
 if not passed:raise ValueError("Phase 6.28 restore drill failed: "+", ".join(audit.loc[audit.status.eq("FAIL"),"target"]))
 return summary|{"summary_json":str(sp)}
