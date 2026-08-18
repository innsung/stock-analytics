import pandas as pd
from src.ml.phase613_related_party_rights_participation_v321 import GROUPS,EXPECTED_PARTICIPANT,audit_related_party_rights_participation_v321
SHARES={r:shares for _,(_,rs,shares,_) in GROUPS.items() for r in rs}
class Dart:
 def document_texts(self,r):
  shares,party=SHARES[r],EXPECTED_PARTICIPANT[r];return [{"name":"x.xml","text":f"특수관계인의 유상증자 참여 유상증자 참여자 {party} 회사와의 관계 계열회사 출자주식수 유상증자주식수 {shares}"}]
def test_resolves_related_party_participation_as_followups(tmp_path):
 ids=[x for qids,_,_,_ in GROUPS.values() for x in qids];rs=[x for _,receipts,_,_ in GROUPS.values() for x in receipts]
 pd.DataFrame({"queue_event_id":ids}).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"rcept_no":r,"report_nm":"특수관계인의유상증자참여"} for r in rs]).to_csv(tmp_path/"d.csv",index=False)
 result=audit_related_party_rights_participation_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert result["not_applicable_evidence_rows"]==5
