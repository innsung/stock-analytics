import pandas as pd

from src.ml.market_effective_date_v321 import _clean_date
from src.ml.phase545_market_adjustment_candidate_selector_v321 import select_market_adjustment_candidates_v321


def test_selects_unique_receipts_and_normalizes_korean_date(tmp_path):
    manifest, official, output = tmp_path / "m.csv", tmp_path / "c.csv", tmp_path / "o.csv"
    pd.DataFrame([
        {"candidate_rcept_no": "1", "acquisition_status": "OFFICIAL_CANDIDATE_AVAILABLE"},
        {"candidate_rcept_no": "1", "acquisition_status": "OFFICIAL_CANDIDATE_AVAILABLE"},
    ]).to_csv(manifest, index=False)
    pd.DataFrame([{"rcept_no": "1", "action_type_hint": "BONUS"}]).to_csv(official, index=False)
    result = select_market_adjustment_candidates_v321(
        candidate_manifest_csv=str(manifest), official_candidates_csv=str(official), output_csv=str(output))
    assert result["selected_candidates"] == 1
    assert _clean_date("2026년 06월 05일") == "20260605"
