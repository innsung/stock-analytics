import json
import pandas as pd

from src.ml.phase549_spinoff_valuation_audit_v321 import audit_listed_spinoff_valuation_v321


def test_audits_parent_factor_but_blocks_total_return_promotion(tmp_path):
    official, output = tmp_path / "official.csv", tmp_path / "audit.csv"
    pd.DataFrame([{"rcept_no": "r", "raw_json": json.dumps({
        "dv_rt": "분할존속회사 : 0.65\n분할신설회사 : 0.35"})}]).to_csv(official, index=False)

    def loader(start, end, code, adjusted):
        if code == "child":
            return pd.DataFrame({"종가": [400.0], "거래량": [10]}, index=pd.to_datetime(["2025-11-24"]))
        closes = [1000.0, 1490.0] if not adjusted else [1500.0, 1490.0]
        return pd.DataFrame({"종가": closes, "거래량": [10, 10]},
                            index=pd.to_datetime(["2025-10-29", "2025-11-24"]))

    result = audit_listed_spinoff_valuation_v321(
        official_candidates_csv=str(official), output_csv=str(output), receipt_no="r",
        parent_code="parent", child_code="child", price_loader=loader)
    row = pd.read_csv(output).iloc[0]
    assert result["factor"] == 1.5
    assert row["distributed_value_reconstruction"] == 1108.5
    assert row["strict_promotion_status"] == "NOT_PROMOTED"
