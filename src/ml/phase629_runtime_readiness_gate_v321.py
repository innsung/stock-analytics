from __future__ import annotations
import importlib,importlib.metadata,json,re,subprocess,sys
from pathlib import Path
import pandas as pd

IMPORTS={"requests":"requests","python-dotenv":"dotenv","pandas":"pandas","numpy":"numpy","pytest":"pytest","scikit-learn":"sklearn","joblib":"joblib","pykrx":"pykrx","beautifulsoup4":"bs4"}
COMMANDS={"build-release-quality-gate-v321","verify-release-artifact-integrity-v321","verify-release-restore-drill-v321"}
def build_runtime_readiness_gate_v321(*,requirements_lock:str,main_py:str,quality_summary_json:str,integrity_summary_json:str,restore_summary_json:str,audit_output_csv:str,summary_json:str)->dict:
 rows=[];python_ok=sys.version_info[:2]==(3,12);rows.append({"check":"PYTHON_VERSION","target":"python","status":"PASS" if python_ok else "FAIL","detail":sys.version.split()[0]})
 lock={}
 for line in Path(requirements_lock).read_text(encoding="utf-8").splitlines():
  m=re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)",line.strip())
  if m:lock[m.group(1).lower()]=m.group(2)
 for package,module in IMPORTS.items():
  expected=lock.get(package);actual="";import_ok=False
  try:actual=importlib.metadata.version(package);importlib.import_module(module);import_ok=True
  except Exception:pass
  ok=import_ok and expected==actual;rows.append({"check":"LOCKED_DEPENDENCY","target":package,"status":"PASS" if ok else "FAIL","detail":f"expected={expected};actual={actual};import={import_ok}"})
 pip=subprocess.run([sys.executable,"-m","pip","check"],capture_output=True,text=True);rows.append({"check":"PIP_CHECK","target":"environment","status":"PASS" if pip.returncode==0 else "FAIL","detail":((pip.stdout+pip.stderr).strip())})
 main=Path(main_py).read_text(encoding="utf-8");missing=sorted(c for c in COMMANDS if c not in main);rows.append({"check":"OPERATIONS_CLI_REGISTERED","target":main_py,"status":"PASS" if not missing else "FAIL","detail":"missing="+",".join(missing)})
 summaries=[("QUALITY_GATE",quality_summary_json,"release_gate"),("INTEGRITY_GATE",integrity_summary_json,"integrity_status"),("RESTORE_GATE",restore_summary_json,"restore_drill")]
 for name,path,key in summaries:
  payload=json.loads(Path(path).read_text(encoding="utf-8"));ok=payload.get(key)=="PASS";rows.append({"check":name,"target":path,"status":"PASS" if ok else "FAIL","detail":f"{key}={payload.get(key)}"})
 audit=pd.DataFrame(rows);passed=audit.status.eq("PASS").all();ap,sp=Path(audit_output_csv),Path(summary_json);ap.parent.mkdir(parents=True,exist_ok=True);audit.to_csv(ap,index=False,encoding="utf-8-sig");summary={"phase":"V3.2.1 Phase 6.29","runtime_readiness":"PASS" if passed else "FAIL","checks_total":len(audit),"checks_passed":int(audit.status.eq("PASS").sum()),"python_version":sys.version.split()[0],"locked_dependencies":len(IMPORTS),"audit_output_csv":str(ap),"fail_closed":True};sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
 if not passed:raise ValueError("Phase 6.29 runtime readiness failed: "+", ".join(audit.loc[audit.status.eq("FAIL"),"target"]))
 return summary|{"summary_json":str(sp)}
