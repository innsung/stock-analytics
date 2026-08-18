import pandas as pd

from src.ml.phase535_kind_paired_strict_evidence_v321 import build_paired_kind_market_observations_v321


def test_builds_valid_paired_observation(tmp_path, monkeypatch):
    pairing, parsed, output, audit = [tmp_path / x for x in ("p.csv", "d.csv", "o.csv", "a.csv")]
    pd.DataFrame([{"code": "55550", "company_name": "신한지주",
        "market_notice_url": "https://kind.krx.co.kr/external/2026/04/28/x.htm",
        "market_kind_acpt_no": "20260428000630", "decision_kind_acpt_no": "20260423000321",
        "decision_kind_doc_no": "20260420000610", "status": "ACQUIRED"}]).to_csv(pairing, index=False)
    pd.DataFrame([{"kind_acpt_no": "20260423000321", "kind_doc_no": "20260420000610",
        "common_cash_amount": "740", "record_date": "20260430", "parse_status": "SUCCESS"}]).to_csv(parsed, index=False)
    class Response:
        status_code = 200; encoding = "utf-8"; apparent_encoding = "utf-8"
        text = "<table><tr><td>회사명</td><td>신한지주</td></tr><tr><td>4. 적용일</td><td>2026-04-29</td></tr></table>"
        def raise_for_status(self): return None
    monkeypatch.setattr("src.ml.phase535_kind_paired_strict_evidence_v321.requests.get", lambda *a, **k: Response())
    result = build_paired_kind_market_observations_v321(
        pairing_csv=str(pairing), parsed_decisions_csv=str(parsed), output_csv=str(output), audit_csv=str(audit))
    assert result["valid_observations"] == 1
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["market_ex_date"] == "20260429"
    assert row["candidate_cash_amount"] == "740"


def test_accepts_official_membership_attachment(tmp_path, monkeypatch):
    pairing, parsed, output, audit = [tmp_path / x for x in ("p.csv", "d.csv", "o.csv", "a.csv")]
    pd.DataFrame([{"code": "51900", "company_name": "LG생활건강",
        "market_notice_url": "https://kind.krx.co.kr/external/2026/03/27/x.htm",
        "market_membership_reference": "https://kind.krx.co.kr/external/list.pdf",
        "market_kind_acpt_no": "20260327002209", "decision_kind_acpt_no": "20260128000534",
        "decision_kind_doc_no": "20260126002927", "status": "ACQUIRED"}]).to_csv(pairing, index=False)
    pd.DataFrame([{"kind_acpt_no": "20260128000534", "kind_doc_no": "20260126002927",
        "common_cash_amount": "1000", "record_date": "20260331", "parse_status": "SUCCESS"}]).to_csv(parsed, index=False)
    class Response:
        status_code = 200; encoding = "utf-8"; apparent_encoding = "utf-8"
        text = "<p>결산배당락 종목: LG화학 등. 적용일: 2026-03-30</p>"
        def raise_for_status(self): return None
    monkeypatch.setattr("src.ml.phase535_kind_paired_strict_evidence_v321.requests.get", lambda *a, **k: Response())
    result = build_paired_kind_market_observations_v321(
        pairing_csv=str(pairing), parsed_decisions_csv=str(parsed), output_csv=str(output), audit_csv=str(audit))
    assert result["valid_observations"] == 1
    assert pd.read_csv(output, dtype=str).iloc[0]["market_reference"].endswith("list.pdf")
