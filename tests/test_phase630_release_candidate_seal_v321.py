import json
import pandas as pd
from src.ml.phase630_release_candidate_seal_v321 import build_release_candidate_seal_v321
def test_seals_release_candidate_from_passed_gates(tmp_path):
 statuses=["VERIFIED"]*25+["NOT_APPLICABLE"]*371+["UNRESOLVED"]*3;pd.DataFrame({"resolution_status":statuses}).to_csv(tmp_path/"v.csv",index=False)
 for name,key in [("q","release_gate"),("i","integrity_status"),("r","restore_drill"),("u","runtime_readiness")]: (tmp_path/f"{name}.json").write_text(json.dumps({"phase":name,key:"PASS"}),encoding="utf-8")
 for name in ["release.zip","requirements.txt","lock.txt"]:(tmp_path/name).write_text(name,encoding="utf-8")
 r=build_release_candidate_seal_v321(verification_csv=str(tmp_path/"v.csv"),release_zip=str(tmp_path/"release.zip"),requirements_txt=str(tmp_path/"requirements.txt"),requirements_lock=str(tmp_path/"lock.txt"),quality_summary_json=str(tmp_path/"q.json"),integrity_summary_json=str(tmp_path/"i.json"),restore_summary_json=str(tmp_path/"r.json"),runtime_summary_json=str(tmp_path/"u.json"),audit_output_csv=str(tmp_path/"a.csv"),manifest_output_json=str(tmp_path/"m.json"));assert r["release_id"]=="V3.2.1-RC1" and r["seal_status"]=="PASS" and not r["git_tag_created"]
