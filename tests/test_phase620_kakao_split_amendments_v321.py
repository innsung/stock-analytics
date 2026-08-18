import pandas as pd

from src.ml.phase620_kakao_split_amendments_v321 import TARGETS, audit_kakao_split_amendments_v321


def test_links_kakao_amendments_to_locked_core_audits(tmp_path):
    q=[]; d=[]
    for qid,(date,title,receipt,_) in TARGETS.items():
        q.append({"queue_event_id":qid,"code":"035720","source_reference_date":date,"source_description":title})
        d.append({"code":"035720","rcept_dt":date,"report_nm":title,"rcept_no":receipt,"flr_nm":"카카오"})
    pd.DataFrame(q).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame(d).to_csv(tmp_path/"d.csv",index=False)
    pd.DataFrame([{"queue_event_id":"5f56d4c50c16e2caf51c","controlling_rcept_no":"20210622800450","subsidiary_disclosure":"True","effective_date_candidate":"20210901","applicability_status":"EXPLICIT_SUBSIDIARY_RESTRUCTURING","promotion_status":"NOT_APPLICABLE_EVIDENCE"}]).to_csv(tmp_path/"p590.csv",index=False)
    pd.DataFrame([{"queue_event_id":"2bd2a82cf3b7f796b9cd","rcept_no":"20210701000279","completion_type":"PHYSICAL_SPLIT","newco_allocation":"100%_TO_PARENT","listed_holder_new_shares":"NONE","listed_holder_cash_consideration":"NONE","verification_status":"NOT_APPLICABLE_EVIDENCE"}]).to_csv(tmp_path/"p616.csv",index=False)
    result=audit_kakao_split_amendments_v321(actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),phase590_audit_csv=str(tmp_path/"p590.csv"),phase616_audit_csv=str(tmp_path/"p616.csv"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"]==2
