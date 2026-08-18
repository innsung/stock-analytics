import json
import pandas as pd

from src.ml.phase548_complex_action_semantic_review_v321 import review_complex_corporate_actions_v321


def test_marks_no_share_merger_not_applicable(tmp_path):
    manifest, official, na, audit = [tmp_path / x for x in ("m.csv", "o.csv", "n.csv", "a.csv")]
    pd.DataFrame([{"queue_event_id": "q", "code": "267250", "action_type_hint": "MERGER",
        "candidate_rcept_no": "r", "acquisition_status": "OFFICIAL_CANDIDATE_AVAILABLE"}]).to_csv(manifest, index=False)
    pd.DataFrame([{"rcept_no": "r", "verification_source": "DART", "verification_reference": "r",
        "raw_json": json.dumps({"mg_rt": "1.000000 : 0.000000(무증자합병)",
                                "mgnstk_cstk_cnt": "-", "mgnstk_ostk_cnt": "-"})}]).to_csv(official, index=False)
    result = review_complex_corporate_actions_v321(
        candidate_manifest_csv=str(manifest), official_candidates_csv=str(official),
        not_applicable_csv=str(na), audit_csv=str(audit))
    assert result["not_applicable_rows"] == 1
    assert pd.read_csv(na, dtype=str).iloc[0]["queue_event_id"] == "q"
