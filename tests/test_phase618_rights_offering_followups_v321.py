import pandas as pd

from src.ml.phase618_rights_offering_followups_v321 import TARGETS, audit_rights_offering_followups_v321


def test_resolves_only_exact_rights_followup_chain(tmp_path):
    queue = []
    disclosures = []
    for qid, (code, date, title, receipt) in TARGETS.items():
        queue.append({"queue_event_id": qid, "code": code, "source_reference_date": date, "source_description": title})
        disclosures.append({"code": code, "rcept_dt": date, "report_nm": title, "rcept_no": receipt})
    pd.DataFrame(queue).to_csv(tmp_path / "q.csv", index=False)
    pd.DataFrame(disclosures).to_csv(tmp_path / "d.csv", index=False)
    result = audit_rights_offering_followups_v321(
        actionable_queue_csv=str(tmp_path / "q.csv"), disclosures_csv=str(tmp_path / "d.csv"),
        evidence_output_csv=str(tmp_path / "e.csv"), audit_output_csv=str(tmp_path / "a.csv"),
        summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 8
    assert not pd.read_csv(tmp_path / "a.csv")["separate_market_adjustment_notice"].any()
