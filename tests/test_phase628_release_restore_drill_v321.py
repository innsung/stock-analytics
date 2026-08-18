import hashlib,zipfile
import pandas as pd
from src.ml.phase628_release_restore_drill_v321 import verify_release_restore_drill_v321
def test_extracts_and_verifies_release_bundle(tmp_path):
 ledger=pd.DataFrame([{"queue_event_id":f"q{i}"} for i in range(399)]);ledger.to_csv(tmp_path/"event_verification_resolved_phase625_v321.csv",index=False);pd.DataFrame(columns=["queue_event_id"]).to_csv(tmp_path/"actionable_resolution_queue_phase625_v321.csv",index=False);files=[tmp_path/"event_verification_resolved_phase625_v321.csv",tmp_path/"actionable_resolution_queue_phase625_v321.csv"]
 pd.DataFrame([{"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"size_bytes":p.stat().st_size} for p in files]).to_csv(tmp_path/"m.csv",index=False)
 with zipfile.ZipFile(tmp_path/"r.zip","w") as z:
  for p in files:z.write(p,p.name)
 r=verify_release_restore_drill_v321(release_zip=str(tmp_path/"r.zip"),manifest_csv=str(tmp_path/"m.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert r["restore_drill"]=="PASS" and r["checks_passed"]==4
