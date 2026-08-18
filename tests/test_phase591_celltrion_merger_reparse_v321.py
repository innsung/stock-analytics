import json

import pandas as pd

from src.ml.phase591_celltrion_merger_reparse_v321 import reparse_celltrion_merger_v321


class Provider:
    def ohlcv(self, start, end, code, adjusted):
        return pd.DataFrame({"date": pd.to_datetime(["2023-12-27", "2023-12-28", "2024-01-12"]),
                             "close": [100, 101, 102]})


def test_reparses_final_terms_and_excludes_acquirer_non_factor_event(tmp_path):
    pd.DataFrame([{"queue_event_id": "q", "code": "068270",
                  "applicability_status": "EFFECTIVE_DATE_REPARSE_REQUIRED"}]).to_csv(tmp_path / "a.csv", index=False)
    pd.DataFrame([{"queue_event_id": "q", "controlling_mechanics_rcept_no": "corrected"}]).to_csv(tmp_path / "t.csv", index=False)
    raw = {"mgsc_mgdt": "2023년 12월 28일", "mgsc_nstklstprd": "2024년 01월 12일",
           "mg_rt": "셀트리온 : 셀트리온헬스케어 = 1 : 0.4492620",
           "mgnstk_cstk_cnt": "-", "mgnstk_ostk_cnt": "73,887,750"}
    pd.DataFrame([{"code": "068270", "endpoint": "cmpMgDecsn", "rcept_no": "primary",
                  "raw_json": json.dumps(raw, ensure_ascii=False)}]).to_csv(tmp_path / "o.csv", index=False)
    result = reparse_celltrion_merger_v321(
        Provider(), applicability_audit_csv=str(tmp_path / "a.csv"), terms_csv=str(tmp_path / "t.csv"),
        official_candidates_csv=str(tmp_path / "o.csv"), evidence_output_csv=str(tmp_path / "e.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 1
    audit = pd.read_csv(tmp_path / "audit.csv", dtype=str).iloc[0]
    assert audit["merger_date"] == "20231228"
    assert audit["target_exchange_ratio"] == "0.4492620"
