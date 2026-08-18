import json
import pandas as pd

from src.ml.phase536_company_name_recovery_v321 import recover_acquisition_company_names_v321


def test_recovers_company_name_from_raw_fact(tmp_path):
    manifest, facts, output, audit = [tmp_path / x for x in ("m.csv", "f.csv", "o.csv", "a.csv")]
    pd.DataFrame([{"code": "35420", "flr_nm": "", "acquisition_status": "NEEDS_COMPANY_DISCLOSURE_DISCOVERY"}]).to_csv(manifest, index=False)
    pd.DataFrame([{"code": "35420", "raw_json": json.dumps({"corp_name": "NAVER"})}]).to_csv(facts, index=False)
    result = recover_acquisition_company_names_v321(
        acquisition_manifest_csv=str(manifest), dividend_facts_csv=str(facts),
        output_csv=str(output), audit_csv=str(audit))
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["flr_nm"] == "NAVER"
    assert row["acquisition_status"] == "READY_FOR_KIND_MARKET_SEARCH"
    assert result["recovered_names"] == 1
