import pandas as pd
import pytest

from src.ml.phase537_kind_direct_decision_acquisition_v321 import acquire_direct_kind_dividend_decisions_v321


def test_rejects_incomplete_manifest(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"code": "000270"}]).to_csv(manifest, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        acquire_direct_kind_dividend_decisions_v321(
            manifest_csv=str(manifest), documents_dir=str(tmp_path / "docs"), output_csv=str(tmp_path / "out.csv"))
