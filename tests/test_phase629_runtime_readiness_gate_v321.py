import importlib.metadata,json
from src.ml.phase629_runtime_readiness_gate_v321 import IMPORTS,COMMANDS,build_runtime_readiness_gate_v321
def test_runtime_gate_matches_active_environment(tmp_path):
 (tmp_path/"lock.txt").write_text("\n".join(f"{p}=={importlib.metadata.version(p)}" for p in IMPORTS),encoding="utf-8");(tmp_path/"main.py").write_text("\n".join(COMMANDS),encoding="utf-8")
 for name,key in [("q","release_gate"),("i","integrity_status"),("r","restore_drill")]: (tmp_path/f"{name}.json").write_text(json.dumps({key:"PASS"}),encoding="utf-8")
 r=build_runtime_readiness_gate_v321(requirements_lock=str(tmp_path/"lock.txt"),main_py=str(tmp_path/"main.py"),quality_summary_json=str(tmp_path/"q.json"),integrity_summary_json=str(tmp_path/"i.json"),restore_summary_json=str(tmp_path/"r.json"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert r["runtime_readiness"]=="PASS" and r["checks_passed"]==15
