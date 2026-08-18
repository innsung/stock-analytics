import json

import pandas as pd

from src.ml.phase595_amorepacific_restructuring_v321 import audit_amorepacific_restructuring_v321


class Provider:
    def ohlcv(self, start, end, code, adjusted):
        dates = pd.to_datetime(["2021-08-27", "2021-09-01", "2021-09-17", "2021-09-24"])
        return pd.DataFrame({"종가": [250000, 248000, 246000, 247000]}, index=dates)


def test_promotes_both_target_holder_transactions_to_not_applicable(tmp_path):
    pd.DataFrame([{"queue_event_id": q} for q in (
        "2d54690554bd4b486389", "704428b155d277ae3a09")]).to_csv(tmp_path / "q.csv", index=False)
    rows = [
        {"code": "090430", "endpoint": "stkExtrDecsn", "rcept_no": "20210623000067",
         "raw_json": json.dumps({"extrsc_extrdt": "2021년 09월 01일", "extrsc_nstklstprd": "2021년 09월 17일",
            "extr_rt": "1:0.0046683 주식교환 대상주주 자기주식 95,274주 및 신주 34,269주",
            "extr_tgcmp_cmpnm": "코스비전"}, ensure_ascii=False)},
        {"code": "090430", "endpoint": "cmpMgDecsn", "rcept_no": "20210621000143",
         "raw_json": json.dumps({"mgsc_mgdt": "2021년 09월 01일", "mgsc_nstklstprd": "-",
            "mg_rt": "1:0.1962185", "mgptncmp_cmpnm": "에스트라", "mgnstk_cstk_cnt": "-",
            "mgnstk_ostk_cnt": "-", "ex_sm_r": "자기주식 교부"}, ensure_ascii=False)},
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "c.csv", index=False)
    result = audit_amorepacific_restructuring_v321(
        Provider(), review_queue_csv=str(tmp_path / "q.csv"), official_candidates_csv=str(tmp_path / "c.csv"),
        evidence_output_csv=str(tmp_path / "e.csv"), audit_output_csv=str(tmp_path / "a.csv"),
        summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 2
    assert set(pd.read_csv(tmp_path / "e.csv")["queue_event_id"]) == {
        "2d54690554bd4b486389", "704428b155d277ae3a09"}
