import pandas as pd

from src.ml.phase601_celltrion_merger_followups_v321 import audit_celltrion_merger_followups_v321


class Dart:
    def document_texts(self, receipt):
        base = "셀트리온 셀트리온헬스케어 "
        if receipt == "20230817800229": text = base + "매매거래정지 합병 중요내용공시 2023-08-18"
        elif receipt == "20230818000437": text = base + "합병신주 0.4492620 73,887,750 신주상장 2024-01-12"
        else: text = base + "합병일 2023-12-28 신주상장 2024-01-12 0.4492620 73,887,750"
        return [{"name": "x.xml", "text": text}]


def test_resolves_three_celltrion_followups(tmp_path):
    ids = ["a39756bdc372fe148ca9", "767d92fda3f88dfdae07", "3d0685cd3d663ea1e895"]
    pd.DataFrame({"queue_event_id": ids}).to_csv(tmp_path / "q.csv", index=False)
    pd.DataFrame([{"queue_event_id": "9aceae44b8a5ad259866", "official_rcept_no": "20230817000203",
        "merger_date": "20231228", "new_share_listing_date": "20240112", "target_exchange_ratio": "0.4492620",
        "merger_consideration_new_shares": "73887750", "merger_date_breakpoints": "0", "listing_date_breakpoints": "0",
        "validation_status": "ACQUIRER_SHAREHOLDER_POSITION_UNCHANGED_NO_MARKET_FACTOR"}]).to_csv(tmp_path / "core.csv", index=False)
    result = audit_celltrion_merger_followups_v321(Dart(), actionable_queue_csv=str(tmp_path / "q.csv"),
        phase591_audit_csv=str(tmp_path / "core.csv"), documents_dir=str(tmp_path / "docs"),
        evidence_output_csv=str(tmp_path / "e.csv"), audit_output_csv=str(tmp_path / "a.csv"), summary_json=str(tmp_path / "s.json"))
    assert result["not_applicable_evidence_rows"] == 3
    assert set(pd.read_csv(tmp_path / "e.csv")["queue_event_id"]) == set(ids)
