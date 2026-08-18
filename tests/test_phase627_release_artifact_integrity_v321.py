import hashlib,json,zipfile
import pandas as pd
from src.ml.phase627_release_artifact_integrity_v321 import REQUIRED_ZIP,verify_release_artifact_integrity_v321
def test_verifies_hashes_gate_and_zip(tmp_path,monkeypatch):
 monkeypatch.chdir(tmp_path);p=tmp_path/"artifact.txt";p.write_text("release",encoding="utf-8");pd.DataFrame([{"path":"artifact.txt","sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"size_bytes":p.stat().st_size}]).to_csv("manifest.csv",index=False);Path=__import__('pathlib').Path;Path("gate.json").write_text(json.dumps({"release_gate":"PASS","checks_total":14,"checks_passed":14,"input_rows":399,"accounted_rows":399,"actionable_rows":0}),encoding="utf-8")
 with zipfile.ZipFile("release.zip","w") as z:
  for name in REQUIRED_ZIP:z.writestr(name,"x")
 r=verify_release_artifact_integrity_v321(manifest_csv="manifest.csv",gate_summary_json="gate.json",release_zip="release.zip",audit_output_csv="audit.csv",summary_json="summary.json");assert r["integrity_status"]=="PASS" and r["checks_passed"]==3
