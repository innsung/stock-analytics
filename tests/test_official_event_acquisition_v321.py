import importlib
from pathlib import Path

import pandas as pd

from src.ml.official_event_acquisition_v321 import (
    acquire_official_event_candidates_v321,
    enrich_official_evidence_template_v321,
)


class FakeDart:
    def corp_code_map(self):
        return {"005930": "00126380"}

    def major_event(self, endpoint, corp_code, begin, end):
        if endpoint == "fricDecsn":
            return [{
                "rcept_no": "20200101000001",
                "nstk_asstd": "20200630",
                "nstk_ascnt_ps_ostk": "0.1",
                "bddd": "20200601",
            }]
        if endpoint == "cmpDvDecsn":
            return [{
                "rcept_no": "20200101000002",
                "dvdt": "20201001",
                "bddd": "20200615",
            }]
        return []


def test_acquire_official_candidates_does_not_promote_strict_evidence(tmp_path):
    universe = tmp_path / "u.csv"
    pd.DataFrame([{"code":"005930","enabled":"true"}]).to_csv(universe,index=False)
    result = acquire_official_event_candidates_v321(
        FakeDart(), universe_csv=str(universe), start="20200101", end="20201231",
        output_dir=str(tmp_path/"out"), max_retries=1, sleep_seconds=0,
    )
    assert result["candidate_rows"] == 2
    assert result["strict_evidence_rows"] == 0
    f = pd.read_csv(tmp_path/"out"/"official_event_candidates_v321.csv", dtype=str).fillna("")
    bonus = f[f["endpoint"]=="fricDecsn"].iloc[0]
    assert bonus["official_event_date"] == "20200630"
    assert float(bonus["adjustment_factor_hint"]) == 1.1
    assert bonus["strict_evidence_ready"].lower() == "false"


def test_research_cutoff_caps_end(tmp_path):
    class Capture(FakeDart):
        def __init__(self): self.calls=[]
        def major_event(self, endpoint, corp_code, begin, end):
            self.calls.append((begin,end))
            return []
    d=Capture()
    u=tmp_path/"u.csv"
    pd.DataFrame([{"code":"005930","enabled":"true"}]).to_csv(u,index=False)
    result=acquire_official_event_candidates_v321(
        d, universe_csv=str(u), start="20260101", end="20261231",
        output_dir=str(tmp_path/"out"), max_retries=1, sleep_seconds=0,
    )
    assert all(end=="20260709" for _,end in d.calls)
    assert result["end"]=="20260709"


def test_enrich_adds_candidate_summary_but_not_strict_fields(tmp_path):
    e=tmp_path/"e.csv"
    pd.DataFrame([{
        "queue_event_id":"q1","code":"005930","event_family":"CORPORATE_ACTION",
        "source_reference_date":"20200601","effective_date":"","known_at":"",
        "action_type":"","adjustment_factor":"","cash_amount":"",
        "verification_source":"","verification_reference":"","resolution_note":"",
    }]).to_csv(e,index=False)
    c=tmp_path/"c.csv"
    pd.DataFrame([{
        "code":"005930","event_kind":"BONUS_ISSUE_DECISION",
        "official_event_date":"20200630","official_known_at":"20200601",
        "action_type_hint":"BONUS","adjustment_factor_hint":"1.1",
        "verification_reference":"20200101000001",
    }]).to_csv(c,index=False)
    out=tmp_path/"enriched.csv"
    result=enrich_official_evidence_template_v321(
        evidence_template_csv=str(e), candidate_csv=str(c), output_csv=str(out)
    )
    assert result["rows_with_candidates"]==1
    f=pd.read_csv(out,dtype=str).fillna("")
    assert f.iloc[0]["effective_date"]==""
    assert f.iloc[0]["action_type"]==""
    assert int(f.iloc[0]["official_candidate_count"])==1


def test_main_namespace_contains_phase56_functions():
    m=importlib.import_module("src.main")
    assert hasattr(m,"acquire_official_event_candidates_v321")
    assert hasattr(m,"enrich_official_evidence_template_v321")
