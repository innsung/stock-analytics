import pandas as pd

from src.ml.phase564_samsung_sdi_rights_verification_v321 import verify_samsung_sdi_rights_v321


def test_builds_strict_rights_evidence_from_adjusted_raw_boundary(tmp_path):
    index = pd.to_datetime(["2025-04-09", "2025-04-10"])
    def loader(start, end, code, adjusted):
        values = [168.0, 175.0] if adjusted else [171.5, 175.0]
        return pd.DataFrame({"종가": values}, index=index)
    result = verify_samsung_sdi_rights_v321(
        evidence_output_csv=str(tmp_path / "e.csv"), audit_output_csv=str(tmp_path / "a.csv"),
        allotment_ratio=0.14, first_issue_price=143.0, price_loader=loader)
    evidence = pd.read_csv(tmp_path / "e.csv")
    assert result["effective_date"] == "20250410"
    assert evidence.iloc[0].action_type == "RIGHTS"
    assert evidence.iloc[0].adjustment_factor == result["adjustment_factor"]
    assert result["adjustment_factor"] > 1
