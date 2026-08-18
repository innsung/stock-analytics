import pandas as pd

from src.ml.phase605_ecoprobm_subsidiary_capital_increases_v321 import GROUPS, audit_ecoprobm_subsidiary_capital_increases_v321


class Dart:
    def document_texts(self, receipt):
        return [{"name":"x.xml", "text":"유상증자결정(종속회사의 주요경영사항) 종속회사인 에코프로글로벌 신주의 종류와 수"}]


def test_resolves_all_subsidiary_capital_increase_date_groups(tmp_path):
    ids = sorted({qid for qids, _ in GROUPS.values() for qid in qids})
    receipts = sorted({r for _, rs in GROUPS.values() for r in rs})
    pd.DataFrame({"queue_event_id":ids}).to_csv(tmp_path/"q.csv", index=False)
    pd.DataFrame([{"rcept_no":r, "report_nm":"유상증자결정(종속회사의주요경영사항)"} for r in receipts]).to_csv(tmp_path/"d.csv", index=False)
    result = audit_ecoprobm_subsidiary_capital_increases_v321(Dart(), actionable_queue_csv=str(tmp_path/"q.csv"),
        disclosures_csv=str(tmp_path/"d.csv"), documents_dir=str(tmp_path/"docs"), evidence_output_csv=str(tmp_path/"e.csv"),
        audit_output_csv=str(tmp_path/"a.csv"), summary_json=str(tmp_path/"s.json"))
    assert result["not_applicable_evidence_rows"] == 7
    assert result["date_groups"] == 4
