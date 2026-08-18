import pandas as pd
from src.ml.phase626_release_quality_gate_v321 import build_release_quality_gate_v321
def test_release_gate_passes_complete_partition(tmp_path):
 rows=[]
 for i in range(399):
  status="VERIFIED" if i<25 else "NOT_APPLICABLE" if i<396 else "UNRESOLVED";rows.append({"queue_event_id":f"q{i}","code":"005930","resolution_status":status,"effective_date":"20200102" if status=="VERIFIED" else "","known_at":"20200101" if status=="VERIFIED" else "","action_type":"BONUS" if status=="VERIFIED" else "","adjustment_factor":"2" if status=="VERIFIED" else "","verification_source":"S","verification_reference":"R","resolution_note":"N"})
 pd.DataFrame(rows).to_csv(tmp_path/"v.csv",index=False);pd.DataFrame(columns=["queue_event_id"]).to_csv(tmp_path/"a.csv",index=False);pd.DataFrame([{"queue_event_id":"q396"},{"queue_event_id":"q397"}]).to_csv(tmp_path/"d.csv",index=False);pd.DataFrame([{"queue_event_id":"q398","blocking_items":"X"}]).to_csv(tmp_path/"b.csv",index=False)
 r=build_release_quality_gate_v321(verification_csv=str(tmp_path/"v.csv"),actionable_csv=str(tmp_path/"a.csv"),deferred_csv=str(tmp_path/"d.csv"),blocked_csv=str(tmp_path/"b.csv"),audit_output_csv=str(tmp_path/"audit.csv"),summary_json=str(tmp_path/"s.json"));assert r["release_gate"]=="PASS" and r["checks_passed"]==14
