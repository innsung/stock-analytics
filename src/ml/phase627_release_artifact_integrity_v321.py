from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path
import pandas as pd

REQUIRED_ZIP={"event_verification_resolved_phase625_v321.csv","release_quality_gate_audit_phase626_v321.csv","release_quality_gate_summary_phase626_v321.json","release_artifact_sha256_phase626_v321.csv"}
def _sha256(path:Path)->str:
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def verify_release_artifact_integrity_v321(*,manifest_csv:str,gate_summary_json:str,release_zip:str,audit_output_csv:str,summary_json:str)->dict:
 manifest=pd.read_csv(manifest_csv,dtype=str).fillna("");gate=json.loads(Path(gate_summary_json).read_text(encoding="utf-8"));rows=[]
 for _,r in manifest.iterrows():
  p=Path(r["path"]);exists=p.is_file();size=p.stat().st_size if exists else -1;digest=_sha256(p) if exists else "";ok=exists and size==int(r["size_bytes"]) and digest.lower()==r["sha256"].lower();rows.append({"check":"MANIFEST_FILE","target":str(p),"status":"PASS" if ok else "FAIL","detail":f"exists={exists};size={size};sha256={digest}"})
 gate_ok=gate.get("release_gate")=="PASS" and gate.get("checks_total")==gate.get("checks_passed")==14 and gate.get("input_rows")==gate.get("accounted_rows")==399 and gate.get("actionable_rows")==0
 rows.append({"check":"PHASE626_GATE","target":gate_summary_json,"status":"PASS" if gate_ok else "FAIL","detail":json.dumps(gate,ensure_ascii=False,sort_keys=True)})
 zp=Path(release_zip);zip_ok=False;names=set();error=""
 try:
  with zipfile.ZipFile(zp) as z:names={Path(x).name for x in z.namelist() if not x.endswith("/")};bad=z.testzip();zip_ok=bad is None and REQUIRED_ZIP.issubset(names)
 except Exception as exc:error=f"{type(exc).__name__}:{exc}"
 rows.append({"check":"RELEASE_ZIP_READABLE","target":str(zp),"status":"PASS" if zip_ok else "FAIL","detail":f"entries={len(names)};required={len(REQUIRED_ZIP)};error={error}"})
 audit=pd.DataFrame(rows);passed=audit.status.eq("PASS").all();ap,sp=Path(audit_output_csv),Path(summary_json);ap.parent.mkdir(parents=True,exist_ok=True);audit.to_csv(ap,index=False,encoding="utf-8-sig");summary={"phase":"V3.2.1 Phase 6.27","integrity_status":"PASS" if passed else "FAIL","checks_total":len(audit),"checks_passed":int(audit.status.eq("PASS").sum()),"manifest_files":len(manifest),"release_zip":str(zp),"release_zip_entries":len(names),"audit_output_csv":str(ap),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
 if not passed:raise ValueError("Phase 6.27 release integrity failed: "+", ".join(audit.loc[audit.status.eq("FAIL"),"target"]))
 return summary|{"summary_json":str(sp)}
