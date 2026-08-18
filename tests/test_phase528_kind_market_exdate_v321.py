import pandas as pd

from src.ml.phase528_kind_market_exdate_v321 import acquire_kind_market_exdates_v321


def test_acquire_kind_market_exdate(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.csv"
    facts = tmp_path / "facts.csv"
    output = tmp_path / "output.csv"
    audit = tmp_path / "audit.csv"
    pd.DataFrame([{
        "code": "660", "company_name": "SK하이닉스",
        "source_url": "https://kind.krx.co.kr/external/2026/05/27/x.htm",
        "expected_record_date": "20260531",
    }]).to_csv(manifest, index=False)
    pd.DataFrame([{
        "code": "000660", "kind_acpt_no": "20260422000788",
        "common_cash_amount": "375", "record_date": "20260531",
    }]).to_csv(facts, index=False)

    class Response:
        status_code = 200
        url = "https://kind.krx.co.kr/external/2026/05/27/x.htm"
        encoding = "utf-8"
        apparent_encoding = "utf-8"
        text = "<table><tr><td>회사명</td><td>SK하이닉스</td></tr><tr><td>4. 적용일</td><td>2026-05-28</td></tr></table>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("src.ml.phase528_kind_market_exdate_v321.requests.get", lambda *a, **k: Response())
    result = acquire_kind_market_exdates_v321(
        manifest_csv=str(manifest), official_facts_csv=str(facts),
        output_csv=str(output), audit_csv=str(audit),
    )
    assert result["acquired_rows"] == 1
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["market_ex_date"] == "20260528"
    assert row["candidate_cash_amount"] == "375"
