import pandas as pd

from src.ml.phase604_hd_ksoe_subsidiary_zero_ratio_merger_v321 import audit_hd_ksoe_subsidiary_zero_ratio_merger_v321


class Dart:
    def document_texts(self, receipt):
        return [{"name":"x.xml", "text":"HD현대중공업은 HD현대중공업모스 지분 100%를 보유하며 합병비율 1.0000000 : 0.0000000 무증자 방식으로 발행할 신주는 없습니다"}]


def test_resolves_parent_disclosure_for_subsidiary_zero_ratio_merger(tmp_path):
    pd.DataFrame([{"queue_event_id":"be3607ed8285bb9a1295"}]).to_csv(tmp_path/"q.csv", index=False)
    title = "주요사항보고서(회사합병결정)(자회사의 주요경영사항)"
    pd.DataFrame([{"rcept_no":"20231026800280", "report_nm":"[첨부정정]"+title},
                  {"rcept_no":"20231025800531", "report_nm":title}]).to_csv(tmp_path/"d.csv", index=False)
    result = audit_hd_ksoe_subsidiary_zero_ratio_merger_v321(Dart(), actionable_queue_csv=str(tmp_path/"q.csv"),
        disclosures_csv=str(tmp_path/"d.csv"), documents_dir=str(tmp_path/"docs"), evidence_output_csv=str(tmp_path/"e.csv"),
        audit_output_csv=str(tmp_path/"a.csv"), summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"] == 1
