import pandas as pd

from src.ml.phase594_samsung_heavy_rights_verification_v321 import verify_samsung_heavy_rights_v321


class Dart:
    def document_texts(self, receipt):
        return [{"name": "price.xml", "text": "<table><tr><td>보통주식(원)</td><td>5,130</td></tr></table>"}]


class Provider:
    def ohlcv(self, start, end, code, adjusted):
        index = pd.to_datetime(["2021-09-15", "2021-09-16", "2021-09-17"])
        # raw_pre=6000, theoretical adjusted_pre ~=5782.1; factor ~=1.03768.
        values = [6000.0, 5800.0, 5900.0] if not adjusted else [5782.1, 5800.0, 5900.0]
        return pd.DataFrame({"종가": values}, index=index)


def test_verifies_pit_rights_terms_and_market_boundary(tmp_path):
    pd.DataFrame([{"queue_event_id": "5432bce5e1925c59ed3b"}]).to_csv(tmp_path / "review.csv", index=False)
    (tmp_path / "decisions").mkdir()
    (tmp_path / "decisions" / "20211028000438_00.xml").write_text(
        "<table><tr><td>확정발행가 보통주식 (원)</td><td>5,130</td></tr>"
        "<tr><td>신주배정기준일</td><td>2021년 09월 17일</td></tr>"
        "<tr><td>1주당 신주배정주식수 (주)</td><td>0.3310433870</td></tr></table>", encoding="utf-8")
    result = verify_samsung_heavy_rights_v321(
        Dart(), Provider(), review_queue_csv=str(tmp_path / "review.csv"),
        decision_documents_dir=str(tmp_path / "decisions"), output_documents_dir=str(tmp_path / "outdocs"),
        evidence_output_csv=str(tmp_path / "e.csv"), audit_output_csv=str(tmp_path / "a.csv"),
        summary_json=str(tmp_path / "s.json"))
    assert result["strict_evidence_rows"] == 1
    assert pd.read_csv(tmp_path / "e.csv", dtype=str).loc[0, "action_type"] == "RIGHTS"
