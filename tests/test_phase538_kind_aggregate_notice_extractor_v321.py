import pandas as pd

from src.ml.phase538_kind_aggregate_notice_extractor_v321 import extract_kind_aggregate_market_targets_v321


def test_extracts_named_target_only(tmp_path, monkeypatch):
    sources, acquisition, output, audit = [tmp_path / x for x in ("s.csv", "a.csv", "o.csv", "u.csv")]
    pd.DataFrame([{"market_name": "KOSPI", "kind_acpt_no": "1", "kind_doc_no": "2", "source_url": "https://x"}]).to_csv(sources, index=False)
    pd.DataFrame([
        {"code": "51910", "flr_nm": "LG화학", "acquisition_status": "READY_FOR_KIND_MARKET_SEARCH"},
        {"code": "5930", "flr_nm": "삼성전자", "acquisition_status": "READY_FOR_KIND_MARKET_SEARCH"},
    ]).to_csv(acquisition, index=False)
    class Response:
        status_code = 200; encoding = "utf-8"; apparent_encoding = "utf-8"; text = "<p>LG화학 등 적용일 2026.3.30</p>"
        def raise_for_status(self): return None
    monkeypatch.setattr("src.ml.phase538_kind_aggregate_notice_extractor_v321.requests.get", lambda *a, **k: Response())
    result = extract_kind_aggregate_market_targets_v321(
        aggregate_manifest_csv=str(sources), acquisition_manifest_csv=str(acquisition),
        output_csv=str(output), audit_csv=str(audit))
    assert result["matched_codes"] == ["051910"]
