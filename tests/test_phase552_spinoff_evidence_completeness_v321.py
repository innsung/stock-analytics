import json
import pandas as pd

from src.ml.phase552_spinoff_evidence_completeness_v321 import audit_spinoff_evidence_completeness_v321


class FakeDart:
    def document_texts(self, receipt_no):
        return [{"name": "x.xml", "text": "신설회사 1주 미만 단주는 현금으로 지급"}]


def test_records_verified_and_missing_evidence_without_promotion(tmp_path):
    official = tmp_path / "official.csv"
    pd.DataFrame([{"rcept_no": "r", "raw_json": json.dumps({
        "abcr_crrt": "35", "abcr_nstkascnd": "분할비율 0.35",
        "abcr_shstkcnt_rt_at_rs": "1주 미만 단주는 재상장 초일의 종가로 현금으로 지급",
        "abcr_nstklstprd": "2025년 11월 24일",
    })}]).to_csv(official, index=False)
    result = audit_spinoff_evidence_completeness_v321(
        FakeDart(), official_candidates_csv=str(official), output_csv=str(tmp_path / "out.csv"),
        document_path=str(tmp_path / "doc.xml"), receipt_no="r")
    frame = pd.read_csv(tmp_path / "out.csv")
    assert result["verified"] == 4
    assert result["missing"] == 1
    missing = frame[frame.check_item.eq("SURVIVING_LEG_FRACTIONAL_RULE")].iloc[0]
    assert missing.evidence_status == "MISSING"
    assert not result["canonical_position_transfer_ready"]
    assert (tmp_path / "doc.xml").exists()
