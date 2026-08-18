import pandas as pd

from src.ml.phase619_hdhyundai_subsidiary_rights_amendments_v321 import TARGETS, TITLE, audit_hdhyundai_subsidiary_rights_amendments_v321


def test_resolves_exact_hdhyundai_subsidiary_amendments(tmp_path):
    q, d = [], []
    for qid, (date, receipt) in TARGETS.items():
        q.append({"queue_event_id": qid, "code": "267250", "source_reference_date": date, "source_description": TITLE})
        d.append({"code": "267250", "rcept_dt": date, "report_nm": TITLE, "rcept_no": receipt, "flr_nm": "HD현대"})
    pd.DataFrame(q).to_csv(tmp_path / "q.csv", index=False)
    pd.DataFrame(d).to_csv(tmp_path / "d.csv", index=False)
    result = audit_hdhyundai_subsidiary_rights_amendments_v321(
        actionable_queue_csv=str(tmp_path / "q.csv"), disclosures_csv=str(tmp_path / "d.csv"),
        evidence_output_csv=str(tmp_path / "e.csv"), audit_output_csv=str(tmp_path / "a.csv"),
        summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 2
    assert set(pd.read_csv(tmp_path / "e.csv").queue_event_id) == set(TARGETS)
