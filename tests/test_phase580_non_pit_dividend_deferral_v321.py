import pandas as pd

from src.ml.phase580_non_pit_dividend_deferral_v321 import defer_non_pit_dividends_v321


def test_defers_only_explicit_post_exdate_amount_decision(tmp_path):
    pd.DataFrame([{"queue_event_id":"late","code":"1"},{"queue_event_id":"keep","code":"2"}]).to_csv(tmp_path/"q.csv",index=False)
    pd.DataFrame([{"queue_event_id":"late","code":"1","residual_status":"DECISION_DISCLOSED_AFTER_EXDATE"}]).to_csv(tmp_path/"r.csv",index=False)
    pd.DataFrame([{"queue_event_id":"late","first_known_at":"20250131","calendar_search_hint":"20241230",
                   "provenance_status":"NO_PRE_EXDATE_AMOUNT_DISCLOSURE"}]).to_csv(tmp_path/"p.csv",index=False)
    result=defer_non_pit_dividends_v321(actionable_queue_csv=str(tmp_path/"q.csv"),residual_csv=str(tmp_path/"r.csv"),
        provenance_audit_csv=str(tmp_path/"p.csv"),actionable_output_csv=str(tmp_path/"o.csv"),
        deferred_output_csv=str(tmp_path/"d.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"))
    assert result["deferred_non_pit_rows"] == 1
    assert pd.read_csv(tmp_path/"o.csv").loc[0,"queue_event_id"] == "keep"
    audit=pd.read_csv(tmp_path/"a.csv",dtype=str)
    assert audit.loc[0,"resolution_status"] == "UNRESOLVED"
